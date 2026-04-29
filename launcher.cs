using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Reflection;
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
    const string MAIN_EXE = "AirPlayStreamer.exe";

    [STAThread]
    static int Main()
    {
        try
        {
            string baseDir = Path.GetDirectoryName(Application.ExecutablePath);
            string mainExePath = Path.Combine(baseDir, MAIN_EXE);

            if (!File.Exists(mainExePath))
            {
                MessageBox.Show(
                    MAIN_EXE + " bulunamadi!\n\nKonum: " + mainExePath,
                    "AirPlay Streamer - Hata",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }

            // VC++ kontrolu
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
                        "Visual C++ Redistributable kurulumu basarisiz oldu.\n\n" +
                        "Manuel olarak buradan indirip kurabilirsiniz:\n" +
                        VC_REDIST_URL,
                        "AirPlay Streamer - Hata",
                        MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }

                MessageBox.Show(
                    "Kurulum tamamlandi! AirPlay Streamer baslatiliyor.",
                    "AirPlay Streamer",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }

            // Ana uygulamayi baslat
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = mainExePath;
            psi.WorkingDirectory = baseDir;
            psi.UseShellExecute = false;
            Process.Start(psi);

            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show("Hata: " + ex.Message, "AirPlay Streamer",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    static bool IsVCRedistInstalled()
    {
        // Visual C++ 2015-2022 Redistributable x64 kontrolu
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
                        object installed = rk.GetValue("Installed");
                        if (installed != null && Convert.ToInt32(installed) == 1)
                            return true;
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
            // TLS 1.2 zorla (eski Windows icin gerekli)
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
                Exception downloadError = null;
                wc.DownloadFileCompleted += (s, e) => {
                    done = true;
                    downloadError = e.Error;
                };

                wc.DownloadFileAsync(new Uri(VC_REDIST_URL), tempPath);

                while (!done)
                {
                    Thread.Sleep(50);
                    Application.DoEvents();
                }

                if (downloadError != null)
                    throw downloadError;
            }

            progress.SetStatus("Kuruluyor (yonetici izni isteyebilir)...");
            progress.SetProgress(100);
            Application.DoEvents();

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = tempPath;
            psi.Arguments = "/install /quiet /norestart";
            psi.UseShellExecute = true;
            psi.Verb = "runas"; // UAC iste
            Process p = Process.Start(psi);
            p.WaitForExit();

            // 0=basarili, 1638=zaten yuklu, 3010=restart gerekli
            bool ok = (p.ExitCode == 0 || p.ExitCode == 1638 || p.ExitCode == 3010);

            try { File.Delete(tempPath); } catch { }

            if (progress != null) progress.Close();
            return ok;
        }
        catch (Exception ex)
        {
            if (progress != null) progress.Close();
            MessageBox.Show("Indirme hatasi: " + ex.Message, "Hata",
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
        Text = "AirPlay Streamer Kurulumu";
        Width = 420;
        Height = 140;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterScreen;
        MaximizeBox = false;
        MinimizeBox = false;
        BackColor = System.Drawing.Color.FromArgb(26, 26, 46);
        ForeColor = System.Drawing.Color.White;

        label = new Label();
        label.Text = "Hazirlaniyor...";
        label.Left = 20;
        label.Top = 20;
        label.Width = 380;
        label.Height = 20;
        label.ForeColor = System.Drawing.Color.White;
        Controls.Add(label);

        bar = new ProgressBar();
        bar.Left = 20;
        bar.Top = 50;
        bar.Width = 380;
        bar.Height = 24;
        bar.Minimum = 0;
        bar.Maximum = 100;
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
        if (bar.InvokeRequired) bar.Invoke(new Action(() => bar.Value = Math.Min(100, Math.Max(0, v))));
        else bar.Value = Math.Min(100, Math.Max(0, v));
    }
}
