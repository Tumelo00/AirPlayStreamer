import { useCallback, useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ChatHeader } from "./components/ChatHeader";
import { FilePreview } from "./components/FilePreview";
import { MessageInput } from "./components/MessageInput";
import { MessageList } from "./components/MessageList";
import { Settings } from "./components/Settings";
import { Sidebar } from "./components/Sidebar";
import { Terminal } from "./components/Terminal";
import { checkClaudeCli } from "./lib/claude";
import { useChat, newConversation } from "./hooks/useChat";
import { MODELS, type Attachment, type Conversation } from "./lib/types";

type Mode = "chat" | "terminal";

export default function App() {
  const [showSettings, setShowSettings] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [preview, setPreview] = useState<Attachment | null>(null);
  const [mode, setMode] = useState<Mode>("chat");

  const [initial, setInitial] = useState<Conversation>(() =>
    newConversation(MODELS[1].id)
  );
  const [chatKey, setChatKey] = useState(0);

  const verifyCli = useCallback(async () => {
    const s = await checkClaudeCli();
    const ready = s.installed && s.loggedIn;
    setNeedsLogin(!ready);
    if (!ready) setShowSettings(true);
  }, []);

  useEffect(() => {
    verifyCli();
  }, [verifyCli]);

  const handleNewChat = useCallback(() => {
    setInitial(newConversation(MODELS[1].id));
    setChatKey((n) => n + 1);
    setPreview(null);
    setMode("chat");
  }, []);

  useEffect(() => {
    const p = listen("menu:new-chat", () => handleNewChat());
    return () => {
      p.then((unlisten) => unlisten()).catch(() => {});
    };
  }, [handleNewChat]);

  const handleSelect = (c: Conversation) => {
    setInitial(c);
    setChatKey((n) => n + 1);
    setPreview(null);
    setMode("chat");
  };

  const handlePersisted = () => setRefreshKey((n) => n + 1);

  return (
    <div className="flex h-full">
      <Sidebar
        activeId={initial.id}
        onSelect={handleSelect}
        onNew={handleNewChat}
        refreshKey={refreshKey}
      />
      <div className="flex-1 flex min-w-0">
        <div className="flex-1 flex flex-col min-w-0">
          <ModeTabs mode={mode} onChange={setMode} />
          {mode === "chat" ? (
            <ChatPane
              key={chatKey}
              initial={initial}
              needsLogin={needsLogin}
              onOpenSettings={() => setShowSettings(true)}
              onNewChat={handleNewChat}
              onPersisted={handlePersisted}
              onPreview={setPreview}
            />
          ) : (
            <Terminal />
          )}
        </div>
        {mode === "chat" && (
          <FilePreview attachment={preview} onClose={() => setPreview(null)} />
        )}
      </div>
      {showSettings && (
        <Settings
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
    </div>
  );
}

interface ChatPaneProps {
  initial: Conversation;
  needsLogin: boolean;
  onOpenSettings: () => void;
  onNewChat: () => void;
  onPersisted: () => void;
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
  const { conversation, streaming, error, sendMessage, setModel } = useChat(
    initial,
    onPersisted
  );

  return (
    <div className="flex flex-col flex-1 min-w-0">
      <ChatHeader
        model={conversation.model}
        onModelChange={setModel}
        onOpenSettings={onOpenSettings}
        onNewChat={onNewChat}
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
      <MessageInput onSend={sendMessage} disabled={streaming || needsLogin} />
    </div>
  );
}
