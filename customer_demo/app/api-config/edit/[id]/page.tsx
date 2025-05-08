"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SetuLogo } from '@/components/ui/setu-logo';
import { ApiConfig, ApiHeader, ApiParameter, HttpMethod } from '../../../types/api';
import { ArrowLeft } from 'lucide-react';

interface Props {
  params: {
    id: string;
  };
}

export default function EditApiConfigPage({ params }: Props) {
  const router = useRouter();
  const [apiConfig, setApiConfig] = useState<Partial<ApiConfig>>({
    method: 'POST',
    headers: [],
    parameters: []
  });
  const [newHeader, setNewHeader] = useState<Partial<ApiHeader>>({});
  const [newParameter, setNewParameter] = useState<Partial<ApiParameter>>({});

  useEffect(() => {
    // Load existing API config
    const configs = JSON.parse(localStorage.getItem('apiConfigs') || '[]');
    const config = configs.find((c: ApiConfig) => c.id === params.id);
    if (config) {
      setApiConfig(config);
    } else {
      router.push('/dashboard');
    }
  }, [params.id, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Update existing config
    const configs = JSON.parse(localStorage.getItem('apiConfigs') || '[]');
    const updatedConfigs = configs.map((c: ApiConfig) => 
      c.id === params.id ? { ...apiConfig, updatedAt: new Date().toISOString() } : c
    );
    
    localStorage.setItem('apiConfigs', JSON.stringify(updatedConfigs));
    router.push('/dashboard');
  };

  const addHeader = () => {
    if (newHeader.key && newHeader.value) {
      setApiConfig(prev => ({
        ...prev,
        headers: [...(prev.headers || []), { ...newHeader, isRequired: true }] as ApiHeader[]
      }));
      setNewHeader({});
    }
  };

  const addParameter = () => {
    if (newParameter.name && newParameter.type) {
      setApiConfig(prev => ({
        ...prev,
        parameters: [...(prev.parameters || []), { ...newParameter, isRequired: true }] as ApiParameter[]
      }));
      setNewParameter({});
    }
  };

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
                    onChange={e => setApiConfig(prev => ({ ...prev, endpoint: e.target.value }))}
                    placeholder="https://dg.setu.co/api/verify/gst"
                    required
                  />
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
                    <Button type="button" onClick={addHeader}>Add Header</Button>
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
                  <div className="flex space-x-2">
                    <Input
                      value={newParameter.name || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Parameter name"
                    />
                    <select
                      value={newParameter.type || ''}
                      onChange={e => setNewParameter(prev => ({ ...prev, type: e.target.value as any }))}
                      className="border rounded-md"
                    >
                      <option value="">Select type</option>
                      <option value="string">String</option>
                      <option value="number">Number</option>
                      <option value="boolean">Boolean</option>
                      <option value="object">Object</option>
                    </select>
                    <Button type="button" onClick={addParameter}>Add Parameter</Button>
                  </div>
                  <div className="space-y-2">
                    {apiConfig.parameters?.map((param, index) => (
                      <div key={index} className="flex items-center space-x-2 bg-gray-50 p-2 rounded">
                        <span className="font-mono">{param.name} ({param.type})</span>
                        <Button
                          type="button"
                          variant="destructive"
                          onClick={() => setApiConfig(prev => ({
                            ...prev,
                            parameters: prev.parameters?.filter((_, i) => i !== index)
                          }))}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <Button type="submit" className="w-full">Save Changes</Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
} 