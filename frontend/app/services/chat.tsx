import { API_BASE_URL } from "./base";

interface UserMessage {
  thread_id: string;
  text: string;
  context: object;
}

interface BotResponse {
  text: string;
}

interface Parameter {
  name: string;
  type: string;
  required: boolean;
  prompt: string;
}

interface ChatState {
  thread_id: string;
  user_message: {
    thread_id: string;
    text: string;
    channel: string;
    context: Record<string, unknown>;
  };
  bot_message: BotResponse[];
  context: {
    result: Record<string, unknown>;
  };
  intent: {
    id: string;
  };
  parameters: Parameter[];
  extracted_parameters: Record<string, unknown>;
  missing_parameters: string[];
  complete: boolean;
  current_node: string;
  date: string;
  nlu: {
    entities: Record<string, unknown>;
    intent: {
      intent: string;
      confidence: number;
    };
  };
}


export const converse = async (userMessage: UserMessage): Promise<ChatState> => {
  const response = await fetch(`${API_BASE_URL}test/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userMessage),
  });
  return response.json();
}; 

export type { ChatState, UserMessage };