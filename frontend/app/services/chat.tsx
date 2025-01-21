const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

interface UserMessage {
  thread_id: string;
  text: string;
  context: object;
}

interface BotResponse {
  text: string;
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
  parameters: any[];
  extracted_parameters: Record<string, unknown>;
  missing_parameters: any[];
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
  const response = await fetch(`${API_BASE_URL}admin/test/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userMessage),
  });
  return response.json();
}; 

export type { ChatState, UserMessage };