const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';

export interface Integration {
  integration_name: string;
  status: boolean;
  settings: Record<string, any>;
}

export async function listIntegrations(): Promise<Integration[]> {
  const response = await fetch(`${baseUrl}/admin/integrations/`);
  if (!response.ok) {
    throw new Error('Failed to fetch integrations');
  }
  return response.json();
}

export async function getIntegration(integrationName: string): Promise<Integration> {
  const response = await fetch(`${baseUrl}/admin/integrations/${integrationName}`);
  if (!response.ok) {
    throw new Error('Failed to fetch integration');
  }
  return response.json();
}

export async function updateIntegration(integrationName: string, data: { status: boolean; settings?: Record<string, any> }): Promise<Integration> {
  const response = await fetch(`${baseUrl}/admin/integrations/${integrationName}`, {
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