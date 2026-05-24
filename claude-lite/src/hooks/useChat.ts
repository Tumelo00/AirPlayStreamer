import { useCallback, useState } from "react";
import { sendMessageStream } from "@/lib/claude";
import { saveConversation } from "@/lib/storage";
import type {
  Attachment,
  Conversation,
  Message,
  ModelId,
} from "@/lib/types";

const newId = () => crypto.randomUUID();

export function useChat(initial: Conversation) {
  const [conversation, setConversation] = useState<Conversation>(initial);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string, attachments: Attachment[] = []) => {
      if (!text.trim() && attachments.length === 0) return;
      setError(null);

      const userMsg: Message = {
        id: newId(),
        role: "user",
        content: text,
        attachments,
        createdAt: Date.now(),
      };
      const assistantMsg: Message = {
        id: newId(),
        role: "assistant",
        content: "",
        createdAt: Date.now(),
      };

      const next: Conversation = {
        ...conversation,
        messages: [...conversation.messages, userMsg, assistantMsg],
        updatedAt: Date.now(),
      };
      setConversation(next);
      setStreaming(true);

      let buffer = "";
      let resolvedSessionId = conversation.sessionId;
      try {
        await sendMessageStream(
          {
            model: conversation.model as ModelId,
            systemPrompt: conversation.systemPrompt,
            sessionId: conversation.sessionId,
            messages: [...conversation.messages, userMsg],
          },
          (e) => {
            if (e.type === "delta" && e.text) {
              buffer += e.text;
              setConversation((c) => ({
                ...c,
                messages: c.messages.map((m) =>
                  m.id === assistantMsg.id ? { ...m, content: buffer } : m
                ),
              }));
            } else if (e.type === "done") {
              if (e.sessionId) resolvedSessionId = e.sessionId;
            } else if (e.type === "error") {
              setError(e.error ?? "Bilinmeyen hata");
            }
          }
        );
      } catch (err) {
        setError(String(err));
      } finally {
        setStreaming(false);
        const finalConv: Conversation = {
          ...next,
          sessionId: resolvedSessionId,
          messages: next.messages.map((m) =>
            m.id === assistantMsg.id ? { ...m, content: buffer } : m
          ),
        };
        setConversation(finalConv);
        saveConversation(finalConv).catch(() => {});
      }
    },
    [conversation]
  );

  const setModel = useCallback((model: string) => {
    setConversation((c) => ({ ...c, model }));
  }, []);

  return { conversation, streaming, error, sendMessage, setModel };
}

export function newConversation(model: string): Conversation {
  return {
    id: newId(),
    title: "Yeni sohbet",
    model,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}
