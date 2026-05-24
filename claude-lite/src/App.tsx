import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ChatHeader } from "./components/ChatHeader";
import { FilePreview } from "./components/FilePreview";
import { MessageInput } from "./components/MessageInput";
import { MessageList } from "./components/MessageList";
import { Settings } from "./components/Settings";
import { Sidebar } from "./components/Sidebar";
import { checkClaudeCli } from "./lib/claude";
import { loadConversation, listConversations } from "./lib/storage";
import {
  loadPreferences,
  savePreferences,
  type Preferences,
} from "./lib/preferences";
import { useChat, newConversation, type PersistEvent } from "./hooks/useChat";
import { MODELS, type Attachment, type Conversation } from "./lib/types";

const Terminal = lazy(() =>
  import("./components/Terminal").then((m) => ({ default: m.Terminal }))
);

type Mode = "chat" | "terminal";

export default function App() {
  const [showSettings, setShowSettings] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [preview, setPreview] = useState<Attachment | null>(null);
  const [mode, setMode] = useState<Mode>("chat");
  const [terminalMounted, setTerminalMounted] = useState(false);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);
  const autoOpenedRef = useRef(false);

  const [initial, setInitial] = useState<Conversation>(() =>
    newConversation(MODELS[1].id)
  );
  const [chatKey, setChatKey] = useState(0);

  useEffect(() => {
    if (mode === "terminal") setTerminalMounted(true);
  }, [mode]);

  useEffect(() => {
    (async () => {
      const p = await loadPreferences();
      setPrefs(p);
      if (p.restoreLastConversation) {
        const list = await listConversations();
        if (list.length > 0) {
          const last = await loadConversation(list[0].id);
          if (last) {
            setInitial(last);
            setChatKey((n) => n + 1);
          }
        }
      }
      setBootstrapped(true);
    })();
  }, []);

  const verifyCli = useCallback(async () => {
    const s = await checkClaudeCli();
    const ready = s.installed && s.loggedIn;
    setNeedsLogin(!ready);
    if (!ready && !autoOpenedRef.current) {
      autoOpenedRef.current = true;
      setShowSettings(true);
    }
  }, []);

  useEffect(() => {
    verifyCli();
  }, [verifyCli]);

  const handleNewChat = useCallback(() => {
    setInitial(newConversation(prefs?.defaultModel ?? MODELS[1].id, prefs?.defaultSystemPrompt));
    setChatKey((n) => n + 1);
    setPreview(null);
    setMode("chat");
  }, [prefs]);

  useEffect(() => {
    const p = listen("menu:new-chat", () => handleNewChat());
    return () => {
      p.then((unlisten) => unlisten()).catch(() => {});
    };
  }, [handleNewChat]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (key === "n") {
        e.preventDefault();
        handleNewChat();
      } else if (key === ",") {
        e.preventDefault();
        setShowSettings(true);
      } else if (key === "t" && !e.shiftKey) {
        e.preventDefault();
        setMode((m) => (m === "chat" ? "terminal" : "chat"));
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleNewChat]);

  const handleSelect = (c: Conversation) => {
    setInitial(c);
    setChatKey((n) => n + 1);
    setPreview(null);
    setMode("chat");
  };

  const handlePersisted = useCallback((event: PersistEvent) => {
    if (event.isNew || event.titleChanged) {
      setRefreshKey((n) => n + 1);
    }
  }, []);

  const handlePrefsChange = useCallback(async (p: Preferences) => {
    setPrefs(p);
    await savePreferences(p);
  }, []);

  if (!bootstrapped) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-500 text-sm">
        Yükleniyor…
      </div>
    );
  }

  return (
    <div className={`flex h-full ${prefs?.theme === "light" ? "theme-light" : ""}`}>
      <Sidebar
        activeId={initial.id}
        onSelect={handleSelect}
        onNew={handleNewChat}
        refreshKey={refreshKey}
      />
      <div className="flex-1 flex min-w-0">
        <div className="flex-1 flex flex-col min-w-0">
          <ModeTabs mode={mode} onChange={setMode} />
          <div
            className="flex-1 flex flex-col min-h-0"
            style={{ display: mode === "chat" ? "flex" : "none" }}
          >
            <ChatPane
              key={chatKey}
              initial={initial}
              needsLogin={needsLogin}
              onOpenSettings={() => setShowSettings(true)}
              onNewChat={handleNewChat}
              onPersisted={handlePersisted}
              onPreview={setPreview}
            />
          </div>
          <div
            className="flex-1 flex flex-col min-h-0"
            style={{ display: mode === "terminal" ? "flex" : "none" }}
          >
            {terminalMounted && (
              <Suspense
                fallback={
                  <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
                    Terminal yükleniyor…
                  </div>
                }
              >
                <Terminal cwd={prefs?.workspaceDir} />
              </Suspense>
            )}
          </div>
        </div>
        {mode === "chat" && (
          <FilePreview attachment={preview} onClose={() => setPreview(null)} />
        )}
      </div>
      {showSettings && prefs && (
        <Settings
          prefs={prefs}
          onPrefsChange={handlePrefsChange}
          onClose={() => {
            setShowSettings(false);
            verifyCli();
          }}
        />
      )}
    </div>
  );
}

function ModeTabs({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="flex border-b border-zinc-800 bg-zinc-900/30 px-2 pt-1.5">
      {(["chat", "terminal"] as const).map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={`text-xs px-3 py-1.5 rounded-t border-b-2 -mb-px transition ${
            mode === m
              ? "border-blue-500 text-zinc-100 bg-zinc-900/60"
              : "border-transparent text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {m === "chat" ? "Sohbet" : "Terminal"}
        </button>
      ))}
      <div className="ml-auto text-[10px] text-zinc-600 self-center pr-2">
        ⌘N · ⌘T · ⌘, · ⌘⇧Space
      </div>
    </div>
  );
}

interface ChatPaneProps {
  initial: Conversation;
  needsLogin: boolean;
  onOpenSettings: () => void;
  onNewChat: () => void;
  onPersisted: (e: PersistEvent) => void;
  onPreview: (a: Attachment) => void;
}

function ChatPane({
  initial,
  needsLogin,
  onOpenSettings,
  onNewChat,
  onPersisted,
  onPreview,
}: ChatPaneProps) {
  const {
    conversation,
    streaming,
    error,
    usage,
    sendMessage,
    stop,
    setModel,
    setSystemPrompt,
  } = useChat(initial, onPersisted);

  return (
    <div className="flex flex-col flex-1 min-w-0">
      <ChatHeader
        model={conversation.model}
        systemPrompt={conversation.systemPrompt}
        onSystemPromptChange={setSystemPrompt}
        onModelChange={setModel}
        onOpenSettings={onOpenSettings}
        onNewChat={onNewChat}
        usage={usage}
      />
      <MessageList
        messages={conversation.messages}
        streaming={streaming}
        onAttachmentClick={onPreview}
      />
      {error && (
        <div className="px-4 py-2 text-sm text-red-400 bg-red-950/30 border-t border-red-900/50">
          {error}
        </div>
      )}
      <MessageInput
        onSend={sendMessage}
        onStop={stop}
        streaming={streaming}
        disabled={needsLogin}
      />
    </div>
  );
}
