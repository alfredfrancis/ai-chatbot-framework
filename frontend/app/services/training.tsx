import { API_BASE_URL } from "./base";

interface Parameter {
  name: string;
  value?: string;
  required?: boolean;
  type?: string;
}

interface Intent {
  nam?: string;
  parameters?: Parameter[];
  responses?: string[];
  [key: string]: unknown;
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

interface EntityValue{
  value: string;
  synonyms: string[];
}

interface EntityModel {
  id?: string;
  name: string;
  entity_values: EntityValue[];
}

interface IntentModel {
  id?: string;
  name: string;
  description?: string;
  intentId: string;
  userDefined?: boolean;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    prompt?: string;
  }>;
  speechResponse: string;
  apiTrigger: boolean;
  apiDetails?: {
    isJson: boolean;
    url: string;
    headers: Array<{
      headerKey: string;
      headerValue: string;
    }>;
    requestType: string;
    jsonData: string;
  };
}

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
  const response = await fetch(`${API_BASE_URL}train/build_models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return response.json();
};

export type { Entity, Example, EntityModel,EntityValue, IntentModel, Parameter, Intent }; 