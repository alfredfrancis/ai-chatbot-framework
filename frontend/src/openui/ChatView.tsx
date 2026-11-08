import { Renderer, type ActionEvent, type OpenUIError } from "@openuidev/react-lang";
import { useCallback, useState } from "react";
import { openuiLibrary } from "./library";

/**
 * A view the agent put in a chat reply: an ```openui fenced block rendered with the same component library as
 * personal apps. It has no tools (no Query, Mutation or Board); a button's @ToAssistant sends its text into
 * this chat as the user's next message.
 */
export default function ChatView({ source, streaming, onPrompt }: { source: string; streaming: boolean; onPrompt: (text: string) => void }) {
  const [problems, setProblems] = useState<string[]>([]);
  const onAction = useCallback((e: ActionEvent) => {
    if (e.type === "continue_conversation") {
      const context = e.params?.context;
      onPrompt(e.humanFriendlyMessage + (context !== undefined ? `\n\nContext: ${JSON.stringify(context)}` : ""));
    } else if (e.type === "open_url") {
      const url = String(e.params?.url ?? "");
      if (/^https?:\/\//.test(url)) window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [onPrompt]);
  const onError = useCallback((errors: OpenUIError[]) => {
    setProblems(errors.filter((e) => e.severity !== "warning").map((e) => [e.code, e.message].filter(Boolean).join(": ")));
  }, []);
  return (
    <div className="oui-chat" data-testid="chat-view">
      <Renderer response={source} library={openuiLibrary} isStreaming={streaming} onAction={onAction} onError={onError} />
      {!streaming && problems.length > 0 && (
        <details className="oui-collapsible">
          <summary>This view has problems</summary>
          <ul className="oui-problems">{problems.slice(0, 5).map((p, i) => <li key={i}>{p}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
