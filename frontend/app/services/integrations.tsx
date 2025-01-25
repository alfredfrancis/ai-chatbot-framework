const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';

export interface FacebookSettings {
  verify: string;
  secret: string;
  page_access_token: string;
}

// eslint-disable-next-line
export interface WebSettings {
}

export interface Integration {
  id: string;
  name: string;
  description: string;
  status: boolean;
}

export interface IntegrationDetails<T> extends Integration {
  settings: T;
}

export async function listIntegrations(): Promise<Integration[]> {
  const response = await fetch(`${baseUrl}/admin/integrations/`);
  if (!response.ok) {
    throw new Error('Failed to fetch integrations');
  }
  return response.json();
}

export async function getIntegration<T>(integrationID: string): Promise<IntegrationDetails<T>> {
  const response = await fetch(`${baseUrl}/admin/integrations/${integrationID}`);
  if (!response.ok) {
    throw new Error('Failed to fetch integration');
  }
  return response.json();
}

export async function updateIntegration<T>(
  integrationID: string, 
  data: { 
    status: boolean; 
    settings: T;
  }
): Promise<IntegrationDetails<T>> {
  const response = await fetch(`${baseUrl}/admin/integrations/${integrationID}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to update integration');
  }
  return response.json();
}