interface MongoId {
  $oid: string;
}

interface Entity {
  name: string;
  value: string;
  begin: number;
  end: number;
}

interface Example {
  text: string;
  entities: Entity[];
}

interface EntityModel {
  _id?: MongoId;
  name: string;
  description?: string;
  examples?: string[];
  regex_features?: string[];
  lookup_tables?: string[];
}

interface IntentModel {
  _id?: MongoId;
  name: string;
  description?: string;
  parameters?: Array<{
    name: string;
    type: string;
    required?: boolean;
  }>;
  responses?: string[];
}

interface AgentConfig {
  name: string;
  description?: string;
  language?: string;
  timezone?: string;
  fallback_responses?: string[];
  [key: string]: unknown;
}

interface ChatState {
  currentNode: string;
  complete: boolean | null;
  context: Record<string, unknown>;
  parameters: Array<{
    name: string;
    value?: string;
    required?: boolean;
    type?: string;
  }>;
  extractedParameters: Record<string, unknown>;
  speechResponse: string[];
  intent: Record<string, unknown>;
  input: string;
  missingParameters: Array<{
    name: string;
    type: string;
    required?: boolean;
  }>;
  owner?: string;
  date?: Date;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080/';

export const saveTrainingData = async (intentId: string, data: Example[]) => {
  const response = await fetch(`${API_BASE_URL}train/${intentId}/data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
};

export const getTrainingData = async (intentId: string): Promise<Example[]> => {
  const response = await fetch(`${API_BASE_URL}train/${intentId}/data`);
  return response.json();
};

export const trainModels = async () => {
  const response = await fetch(`${API_BASE_URL}nlu/build_models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return response.json();
};

export type { Entity, Example, EntityModel, IntentModel, AgentConfig, ChatState, MongoId }; 