import { useEffect, useRef } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { openPty, type PtyHandle } from "@/lib/pty";
import "@xterm/xterm/css/xterm.css";

interface Props {
  initialCommand?: string;
  shell?: string;
}

export function Terminal({ initialCommand, shell }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const ptyRef = useRef<PtyHandle | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const term = new XTerm({
      fontFamily:
        '"JetBrains Mono", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
      fontSize: 13,
      lineHeight: 1.3,
      cursorBlink: true,
      theme: {
        background: "#09090b",
        foreground: "#e4e4e7",
        cursor: "#60a5fa",
        selectionBackground: "#3f3f46",
        black: "#27272a",
        red: "#f87171",
        green: "#4ade80",
        yellow: "#fbbf24",
        blue: "#60a5fa",
        magenta: "#c084fc",
        cyan: "#22d3ee",
        white: "#e4e4e7",
      },
      allowProposedApi: true,
    });

    const fit = new FitAddon();
    const links = new WebLinksAddon();
    term.loadAddon(fit);
    term.loadAddon(links);
    term.open(host);
    fit.fit();
    xtermRef.current = term;

    let disposed = false;
    let unData: (() => void) | null = null;
    let unExit: (() => void) | null = null;
    let unInput: { dispose: () => void } | null = null;

    (async () => {
      const handle = await openPty({
        cols: term.cols,
        rows: term.rows,
        shell,
      });
      if (disposed) {
        handle.close().catch(() => {});
        return;
      }
      ptyRef.current = handle;

      unData = await handle.onData((chunk) => {
        term.write(chunk);
      });
      unExit = await handle.onExit(() => {
        term.write("\r\n\x1b[33m[oturum kapandı]\x1b[0m\r\n");
      });
      unInput = term.onData((data) => {
        handle.write(data).catch(() => {});
      });

      if (initialCommand) {
        setTimeout(() => handle.write(initialCommand + "\n").catch(() => {}), 200);
      }
    })();

    const ro = new ResizeObserver(() => {
      try {
        fit.fit();
        const cols = term.cols;
        const rows = term.rows;
        ptyRef.current?.resize(cols, rows).catch(() => {});
      } catch {}
    });
    ro.observe(host);

    return () => {
      disposed = true;
      ro.disconnect();
      unInput?.dispose();
      unData?.();
      unExit?.();
      ptyRef.current?.close().catch(() => {});
      term.dispose();
    };
  }, [initialCommand, shell]);

  return (
    <div className="flex-1 bg-[#09090b] overflow-hidden">
      <div ref={hostRef} className="w-full h-full p-2" />
    </div>
  );
}
