using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("AirPlay Streamer")]
[assembly: AssemblyProduct("AirPlay Streamer")]
[assembly: AssemblyCompany("Tumer Ustunel")]
[assembly: AssemblyCopyright("Copyright (c) 2026 Tumer Ustunel")]
[assembly: AssemblyVersion("1.0.0.0")]

class Launcher
{
    const string VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe";
    const string APP_FOLDER_NAME = "AirPlayStreamer";
    const string MAIN_EXE = "AirPlayStreamer-Core.exe";
    const string PAYLOAD_RESOURCE = "Launcher.app.zip";
    const string VERSION_FILE = "payload.hash";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    static extern bool SetForegroundWindow(IntPtr hWnd);

    [STAThread]
    static int Main()
    {
        try
        {
            // 1. Get app data directory
            string appDataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                APP_FOLDER_NAME);
            string mainExePath = Path.Combine(appDataDir, MAIN_EXE);
            string versionPath = Path.Combine(appDataDir, VERSION_FILE);

            // 2. Re-extract whenever the embedded payload changed.
            // Compare a hash of the bundled zip vs the last extracted hash,
            // so every new build is deployed even with the same version.
            string payloadHash = ComputePayloadHash();
            string cachedHash = "";
            if (File.Exists(versionPath))
            {
                try { cachedHash = File.ReadAllText(versionPath).Trim(); }
                catch { }
            }
            bool needsExtraction = !File.Exists(mainExePath) ||
                                   payloadHash == "" ||
                                   cachedHash != payloadHash;

            if (needsExtraction)
            {
                if (!ExtractPayload(appDataDir))
                {
                    MessageBox.Show(
                        "Uygulama dosyalari cikarilamadi.",
                        "AirPlay Streamer - Hata",
                        MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }
                try { File.WriteAllText(versionPath, payloadHash); }
                catch { }
            }

            if (!File.Exists(mainExePath))
            {
                MessageBox.Show(
                    "Ana uygulama bulunamadi: " + mainExePath,
                    "AirPlay Streamer - Hata",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }

            // 3. Check VC++ Redistributable
            if (!IsVCRedistInstalled())
            {
                DialogResult dr = MessageBox.Show(
                    "AirPlay Streamer'in calismasi icin Microsoft Visual C++ " +
                    "Redistributable gerekli.\n\n" +
                    "Simdi indirip yuklemek istiyor musunuz? (~14 MB)",
                    "AirPlay Streamer - Eksik Bilesen",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Information);

                if (dr != DialogResult.Yes)
                    return 0;

                if (!DownloadAndInstallVCRedist())
                {
                    MessageBox.Show(
                        "Visual C++ Redistributable kurulumu basarisiz.\n\n" +
                        "Manuel: " + VC_REDIST_URL,
                        "AirPlay Streamer - Hata",
                        MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }
            }

            // 4. Single instance: if already running, focus it and exit
            Process[] running = Process.GetProcessesByName("AirPlayStreamer-Core");
            if (running.Length > 0)
            {
                IntPtr hwnd = FindWindow(null, "AirPlay Streamer");
                if (hwnd != IntPtr.Zero)
                {
                    ShowWindow(hwnd, 9);            // SW_RESTORE
                    SetForegroundWindow(hwnd);
                }
                return 0;
            }

            // 5. Launch main app
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = mainExePath;
            psi.WorkingDirectory = appDataDir;
            psi.UseShellExecute = false;
            Process.Start(psi);

            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show("Hata: " + ex.Message + "\n\n" + ex.StackTrace,
                "AirPlay Streamer", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    static string ComputePayloadHash()
    {
        try
        {
            Assembly asm = Assembly.GetExecutingAssembly();
            string resourceName = null;
            foreach (string n in asm.GetManifestResourceNames())
            {
                if (n.EndsWith("app.zip")) { resourceName = n; break; }
            }
            if (resourceName == null) return "";

            using (Stream rs = asm.GetManifestResourceStream(resourceName))
            using (var md5 = System.Security.Cryptography.MD5.Create())
            {
                byte[] hash = md5.ComputeHash(rs);
                return BitConverter.ToString(hash).Replace("-", "");
            }
        }
        catch
        {
            return "";
        }
    }

    static bool ExtractPayload(string targetDir)
    {
        ProgressForm progress = null;
        try
        {
            progress = new ProgressForm();
            progress.SetStatus("Ilk calistirma: Dosyalar hazirlaniyor...");
            progress.SetProgress(0);
            progress.Show();
            Application.DoEvents();

            // Get embedded ZIP
            Assembly asm = Assembly.GetExecutingAssembly();
            string resourceName = null;
            foreach (string n in asm.GetManifestResourceNames())
            {
                if (n.EndsWith("app.zip"))
                {
                    resourceName = n;
                    break;
                }
            }

            if (resourceName == null)
                throw new Exception("Embedded payload bulunamadi");

            // Clean target dir if exists
            if (Directory.Exists(targetDir))
            {
                try { Directory.Delete(targetDir, true); } catch { }
            }
            Directory.CreateDirectory(targetDir);

            progress.SetStatus("Dosyalar cikariliyor (~110 MB)...");
            progress.SetProgress(20);
            Application.DoEvents();

            using (Stream rs = asm.GetManifestResourceStream(resourceName))
            using (ZipArchive zip = new ZipArchive(rs, ZipArchiveMode.Read))
            {
                int total = zip.Entries.Count;
                int done = 0;
                foreach (ZipArchiveEntry entry in zip.Entries)
                {
                    string outPath = Path.Combine(targetDir, entry.FullName);
                    if (string.IsNullOrEmpty(entry.Name))
                    {
                        Directory.CreateDirectory(outPath);
                    }
                    else
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                        entry.ExtractToFile(outPath, true);
                    }
                    done++;
                    if (done % 20 == 0)
                    {
                        progress.SetProgress(20 + (done * 75 / total));
                        Application.DoEvents();
                    }
                }
            }

            progress.SetProgress(100);
            progress.SetStatus("Hazir!");
            Application.DoEvents();
            Thread.Sleep(300);
            progress.Close();
            return true;
        }
        catch (Exception ex)
        {
            if (progress != null) progress.Close();
            MessageBox.Show("Cikarma hatasi: " + ex.Message,
                "Hata", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return false;
        }
    }

    static bool IsVCRedistInstalled()
    {
        string[] keys = {
            @"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            @"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
        };
        foreach (string key in keys)
        {
            try
            {
                using (RegistryKey rk = Registry.LocalMachine.OpenSubKey(key))
                {
                    if (rk != null)
                    {
                        object inst = rk.GetValue("Installed");
                        if (inst != null && Convert.ToInt32(inst) == 1) return true;
                    }
                }
            }
            catch { }
        }
        return false;
    }

    static bool DownloadAndInstallVCRedist()
    {
        string tempPath = Path.Combine(Path.GetTempPath(), "vc_redist.x64.exe");
        ProgressForm progress = null;
        try
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;

            progress = new ProgressForm();
            progress.SetStatus("Visual C++ Redistributable indiriliyor...");
            progress.Show();
            Application.DoEvents();

            using (WebClient wc = new WebClient())
            {
                wc.DownloadProgressChanged += (s, e) => {
                    progress.SetProgress(e.ProgressPercentage);
                    Application.DoEvents();
                };

                bool done = false;
                Exception err = null;
                wc.DownloadFileCompleted += (s, e) => { done = true; err = e.Error; };
                wc.DownloadFileAsync(new Uri(VC_REDIST_URL), tempPath);

                while (!done) { Thread.Sleep(50); Application.DoEvents(); }
                if (err != null) throw err;
            }

            progress.SetStatus("Kuruluyor (yonetici izni isteyebilir)...");
            progress.SetProgress(100);
            Application.DoEvents();

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = tempPath;
            psi.Arguments = "/install /quiet /norestart";
            psi.UseShellExecute = true;
            psi.Verb = "runas";
            Process p = Process.Start(psi);
            p.WaitForExit();

            bool ok = (p.ExitCode == 0 || p.ExitCode == 1638 || p.ExitCode == 3010);
            try { File.Delete(tempPath); } catch { }
            if (progress != null) progress.Close();
            return ok;
        }
        catch (Exception ex)
        {
            if (progress != null) progress.Close();
            MessageBox.Show("Hata: " + ex.Message, "Hata",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return false;
        }
    }
}

class ProgressForm : Form
{
    Label label;
    ProgressBar bar;

    public ProgressForm()
    {
        Text = "AirPlay Streamer";
        Width = 440;
        Height = 150;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterScreen;
        MaximizeBox = false;
        MinimizeBox = false;
        BackColor = System.Drawing.Color.FromArgb(26, 26, 46);
        ForeColor = System.Drawing.Color.White;
        ShowInTaskbar = true;

        Label title = new Label();
        title.Text = "AirPlay Streamer";
        title.Font = new System.Drawing.Font("Segoe UI", 11, System.Drawing.FontStyle.Bold);
        title.Left = 20; title.Top = 15; title.Width = 400; title.Height = 20;
        title.ForeColor = System.Drawing.Color.FromArgb(233, 69, 96);
        Controls.Add(title);

        label = new Label();
        label.Text = "Hazirlaniyor...";
        label.Left = 20; label.Top = 45; label.Width = 400; label.Height = 20;
        label.ForeColor = System.Drawing.Color.White;
        Controls.Add(label);

        bar = new ProgressBar();
        bar.Left = 20; bar.Top = 75; bar.Width = 400; bar.Height = 20;
        bar.Minimum = 0; bar.Maximum = 100;
        Controls.Add(bar);
    }

    public void SetStatus(string s)
    {
        if (label.InvokeRequired) label.Invoke(new Action(() => label.Text = s));
        else label.Text = s;
        Refresh();
    }

    public void SetProgress(int v)
    {
        v = Math.Min(100, Math.Max(0, v));
        if (bar.InvokeRequired) bar.Invoke(new Action(() => bar.Value = v));
        else bar.Value = v;
    }
}
