import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";

export interface PtyHandle {
  id: string;
  onData: (cb: (chunk: string) => void) => Promise<UnlistenFn>;
  onExit: (cb: () => void) => Promise<UnlistenFn>;
  write: (data: string) => Promise<void>;
  resize: (cols: number, rows: number) => Promise<void>;
  close: () => Promise<void>;
}

export async function openPty(opts: {
  id?: string;
  cols: number;
  rows: number;
  shell?: string;
  cwd?: string;
}): Promise<PtyHandle> {
  const id = opts.id ?? crypto.randomUUID();
  await invoke("pty_open", {
    id,
    cols: opts.cols,
    rows: opts.rows,
    shell: opts.shell ?? null,
    cwd: opts.cwd ?? null,
  });

  return {
    id,
    onData: (cb) => listen<string>(`pty:${id}:data`, (e) => cb(e.payload)),
    onExit: (cb) => listen<string>(`pty:${id}:exit`, () => cb()),
    write: (data) => invoke("pty_write", { id, data }),
    resize: (cols, rows) => invoke("pty_resize", { id, cols, rows }),
    close: () => invoke("pty_close", { id }),
  };
}
