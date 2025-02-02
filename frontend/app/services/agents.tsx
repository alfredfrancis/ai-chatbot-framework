import { API_BASE_URL } from "./base";

interface NLUConfig {
  pipeline_type: 'traditional' | 'llm';
  traditional_settings: {
    intent_detection_threshold: number;
    entity_detection_threshold: number;
    use_spacy: boolean;
  };
  llm_settings: {
    base_url: string;
    api_key: string;
    model_name: string;
    max_tokens: number;
    temperature: number;
  };
}

export const getConfig = async (): Promise<NLUConfig> => {
  const response = await fetch(`${API_BASE_URL}bots/default/config`);
  return response.json();
};

export const updateConfig = async (data: NLUConfig): Promise<NLUConfig> => {
  const response = await fetch(`${API_BASE_URL}bots/default/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
};

export const importIntents = async (fileToUpload: File) => {
  const formData = new FormData();
  formData.append('file', fileToUpload, fileToUpload.name);
  const response = await fetch(`${API_BASE_URL}bots/default/import`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};

export const exportIntents = async () => {
  window.location.href = `${API_BASE_URL}bots/default/export`;
};

export type { NLUConfig }; 