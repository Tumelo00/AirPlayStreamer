import { useEffect, useState } from "react";
import { ChatHeader } from "./components/ChatHeader";
import { MessageInput } from "./components/MessageInput";
import { MessageList } from "./components/MessageList";
import { Settings } from "./components/Settings";
import { checkClaudeCli } from "./lib/claude";
import { useChat, newConversation } from "./hooks/useChat";
import { MODELS } from "./lib/types";

export default function App() {
  const [showSettings, setShowSettings] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [resetCounter, setResetCounter] = useState(0);

  const [initial, setInitial] = useState(() =>
    newConversation(MODELS[1].id)
  );

  const { conversation, streaming, error, sendMessage, setModel } =
    useChat(initial);

  const verifyCli = async () => {
    const s = await checkClaudeCli();
    const ready = s.installed && s.loggedIn;
    setNeedsLogin(!ready);
    if (!ready) setShowSettings(true);
  };

  useEffect(() => {
    verifyCli();
  }, []);

  const handleNewChat = () => {
    const fresh = newConversation(conversation.model);
    setInitial(fresh);
    setResetCounter((n) => n + 1);
  };

  return (
    <div key={resetCounter} className="flex flex-col h-full">
      <ChatHeader
        model={conversation.model}
        onModelChange={setModel}
        onOpenSettings={() => setShowSettings(true)}
        onNewChat={handleNewChat}
      />
      <MessageList messages={conversation.messages} streaming={streaming} />
      {error && (
        <div className="px-4 py-2 text-sm text-red-400 bg-red-950/30 border-t border-red-900/50">
          {error}
        </div>
      )}
      <MessageInput onSend={sendMessage} disabled={streaming || needsLogin} />
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
