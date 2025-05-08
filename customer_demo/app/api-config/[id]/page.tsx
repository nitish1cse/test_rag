"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { SetuLogo } from "../../../components/ui/setu-logo";
import { ApiConfig, ApiHeader, ApiParameter, HttpMethod, ParameterType, ParameterLocation } from '../../types/api';
import { ArrowLeft } from 'lucide-react';

export default function EditApiConfig({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [apiConfig, setApiConfig] = useState<Partial<ApiConfig>>({
    method: 'POST',
    headers: [],
    parameters: []
  });
  const [newHeader, setNewHeader] = useState<Partial<ApiHeader>>({});
  const [newParameter, setNewParameter] = useState<Partial<ApiParameter>>({});
  const [endpointPreview, setEndpointPreview] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchApiConfig = async () => {
      try {
        const response = await fetch(`/api/api-configs/${params.id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch API configuration');
        }
        const data = await response.json();
        setApiConfig(data);
        setEndpointPreview(updateEndpointPreview(data));
      } catch (error) {
        console.error('Error fetching API config:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchApiConfig();
  }, [params.id]);

  const updateEndpointPreview = (config: Partial<ApiConfig>) => {
    if (!config.endpoint) return '';
    
    let preview = config.endpoint;
    const pathParams = config.parameters?.filter(p => p.location === 'path') || [];
    const queryParams = config.parameters?.filter(p => p.location === 'query') || [];

    pathParams.forEach(param => {
      preview = preview.replace(`{${param.name}}`, `[${param.name}]`);
    });

    if (queryParams.length > 0) {
      preview += '?' + queryParams
        .map(param => `${param.name}=${param.defaultValue || `[${param.name}]`}`)
        .join('&');
    }

    return preview;
  };

  const handleEndpointChange = (value: string) => {
    const updatedConfig = { ...apiConfig, endpoint: value };
    setApiConfig(updatedConfig);
    setEndpointPreview(updateEndpointPreview(updatedConfig));
  };

  const addParameter = () => {
    if (newParameter.name && newParameter.type && newParameter.location) {
      const updatedConfig = {
        ...apiConfig,
        parameters: [...(apiConfig.parameters || []), { ...newParameter, isRequired: true }] as ApiParameter[]
      };
      setApiConfig(updatedConfig);
      setEndpointPreview(updateEndpointPreview(updatedConfig));
      setNewParameter({});
    }
  };

  const removeParameter = (index: number) => {
    const updatedConfig = {
      ...apiConfig,
      parameters: apiConfig.parameters?.filter((_, i) => i !== index)
    };
    setApiConfig(updatedConfig);
    setEndpointPreview(updateEndpointPreview(updatedConfig));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const response = await fetch(`/api/api-configs/${params.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(apiConfig),
      });

      if (!response.ok) {
        throw new Error('Failed to update API configuration');
      }

      router.push('/dashboard');
    } catch (error) {
      console.error('Error updating API config:', error);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-8 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <div className="flex items-center justify-center w-[32px] h-[32px] rounded-full overflow-hidden bg-gray-50 shadow-sm">
              <SetuLogo size={32} className="object-contain" />
            </div>
            <span className="text-gray-900 text-xl font-semibold">SETU</span>
          </div>
          <Button
            variant="outline"
            onClick={() => router.push('/dashboard')}
            className="border-gray-200 text-gray-700 hover:bg-gray-50"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Edit API Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Label>API Name</Label>
                  <Input
                    value={apiConfig.name || ''}
                    onChange={e => setApiConfig(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="GST Verification API"
                    required
                  />
                </div>

                <div>
                  <Label>Description</Label>
                  <Input
                    value={apiConfig.description || ''}
                    onChange={e => setApiConfig(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Verify GST number validity"
                    required
                  />
                </div>

                <div>
                  <Label>Endpoint</Label>
                  <Input
                    value={apiConfig.endpoint || ''}
                    onChange={e => handleEndpointChange(e.target.value)}
                    placeholder="https://api.example.com/v1/users/{id}"
                    required
                  />
                  {endpointPreview && (
                    <div className="mt-2 text-sm text-gray-500">
                      Preview: {endpointPreview}
                    </div>
                  )}
                </div>

                <div>
                  <Label>Method</Label>
                  <select
                    value={apiConfig.method}
                    onChange={e => setApiConfig(prev => ({ ...prev, method: e.target.value as HttpMethod }))}
                    className="w-full p-2 border rounded-md"
                    required
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <Label>Headers</Label>
                  <div className="flex space-x-2">
                    <Input
                      value={newHeader.key || ''}
                      onChange={e => setNewHeader(prev => ({ ...prev, key: e.target.value }))}
                      placeholder="Header key (e.g., x-client-id)"
                    />
                    <Input
                      value={newHeader.value || ''}
                      onChange={e => setNewHeader(prev => ({ ...prev, value: e.target.value }))}
                      placeholder="Header value"
                    />
                    <Button type="button" onClick={() => {
                      if (newHeader.key && newHeader.value) {
                        setApiConfig(prev => ({
                          ...prev,
                          headers: [...(prev.headers || []), { ...newHeader, isRequired: true }] as ApiHeader[]
                        }));
                        setNewHeader({});
                      }
                    }}>Add Header</Button>
                  </div>
                  <div className="space-y-2">
                    {apiConfig.headers?.map((header, index) => (
                      <div key={index} className="flex items-center space-x-2 bg-gray-50 p-2 rounded">
                        <span className="font-mono">{header.key}: {header.value}</span>
                        <Button
                          type="button"
                          variant="destructive"
                          onClick={() => setApiConfig(prev => ({
                            ...prev,
                            headers: prev.headers?.filter((_, i) => i !== index)
                          }))}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Parameters</Label>
                  <div className="grid grid-cols-5 gap-2">
                    <Input
                      value={newParameter.name || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Parameter name"
                      className="col-span-1"
                    />
                    <select
                      value={newParameter.type || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, type: e.target.value as ParameterType }))}
                      className="col-span-1 border rounded-md"
                    >
                      <option value="">Type</option>
                      <option value="string">String</option>
                      <option value="number">Number</option>
                      <option value="boolean">Boolean</option>
                      <option value="object">Object</option>
                    </select>
                    <select
                      value={newParameter.location || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, location: e.target.value as ParameterLocation }))}
                      className="col-span-1 border rounded-md"
                    >
                      <option value="">Location</option>
                      <option value="path">Path</option>
                      <option value="query">Query</option>
                      <option value="body">Body</option>
                    </select>
                    <Input
                      value={newParameter.defaultValue || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, defaultValue: e.target.value }))}
                      placeholder="Default value"
                      className="col-span-1"
                    />
                    <Button 
                      type="button" 
                      onClick={addParameter}
                      className="col-span-1"
                    >
                      Add
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {apiConfig.parameters?.map((param, index) => (
                      <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium">{param.name}</span>
                          <span className="text-sm text-gray-500">({param.type})</span>
                          <span className="px-2 py-0.5 text-xs rounded bg-gray-200">{param.location}</span>
                          {param.defaultValue && (
                            <span className="text-sm text-gray-500">Default: {param.defaultValue}</span>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeParameter(index)}
                          className="text-red-600 hover:text-red-700"
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <Button type="submit" className="w-full">Update API Configuration</Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
} 