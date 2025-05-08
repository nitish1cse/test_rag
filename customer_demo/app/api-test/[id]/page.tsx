"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { SetuLogo } from "../../../components/ui/setu-logo";
import { ApiConfig } from "../../../types/api";

interface Props {
  params: {
    id: string;
  };
}

export default function ApiTestPage({ params }: Props) {
  const router = useRouter();
  const [apiConfig, setApiConfig] = useState<ApiConfig | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchApiConfig = async () => {
      try {
        const response = await fetch(`/api/api-configs/${params.id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch API configuration');
        }
        const config = await response.json();
        setApiConfig(config);
        
        // Initialize form data with default values
        const initialData: Record<string, any> = {};
        config.parameters.forEach((param: any) => {
          initialData[param.name] = param.defaultValue || '';
        });
        setFormData(initialData);
      } catch (err) {
        console.error('Error fetching API config:', err);
        setError(err instanceof Error ? err.message : 'Failed to load API configuration');
      } finally {
        setLoading(false);
      }
    };

    fetchApiConfig();
  }, [params.id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiConfig) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // Prepare headers
      const headers: Record<string, string> = {};
      apiConfig.headers.forEach(header => {
        headers[header.key] = header.value;
      });

      // Make request through our proxy endpoint
      const response = await fetch('/api/proxy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          endpoint: apiConfig.endpoint,
          method: apiConfig.method,
          headers: headers,
          data: formData
        })
      });

      let data;
      try {
        data = await response.json();
      } catch (e) {
        throw new Error('Invalid response format');
      }

      console.log('API Response:', data);
      setResponse(data);
      
      if (!response.ok) {
        throw new Error(
          typeof data === 'object' && data.error 
            ? data.error 
            : `API request failed with status ${response.status}`
        );
      }
    } catch (err) {
      console.error('API call error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred while making the API call');
    } finally {
      setLoading(false);
    }
  };

  if (!apiConfig) {
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
            Back to Dashboard
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8">
        <div className="flex flex-col space-y-4">
          <h1 className="text-2xl font-bold text-gray-900">{apiConfig.name}</h1>
          <p className="text-gray-500">{apiConfig.description}</p>
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Test Form */}
          <Card>
            <CardHeader>
              <CardTitle>Test API</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {apiConfig.parameters
                  .filter(param => !param.defaultValue) // Only show parameters without default values
                  .map((param, index) => (
                    <div key={index}>
                      <Label>{param.name}</Label>
                      <Input
                        value={formData[param.name] || ''}
                        onChange={e => setFormData(prev => ({
                          ...prev,
                          [param.name]: e.target.value
                        }))}
                        placeholder={`Enter ${param.name}`}
                        required={param.isRequired}
                      />
                    </div>
                  ))}

                {/* Show default parameters in disabled state */}
                {apiConfig.parameters
                  .filter(param => param.defaultValue)
                  .length > 0 && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-md">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">Default Parameters</h3>
                      {apiConfig.parameters
                        .filter(param => param.defaultValue)
                        .map((param, index) => (
                          <div key={index} className="flex justify-between items-center text-sm text-gray-500">
                            <span>{param.name}</span>
                            <span className="font-mono">{param.defaultValue}</span>
                          </div>
                        ))}
                    </div>
                  )}

                <Button
                  type="submit"
                  className="w-full bg-[#5e65de] hover:bg-[#4a51c4]"
                  disabled={loading}
                >
                  {loading ? 'Testing API...' : 'Test API'}
                </Button>

                {error && (
                  <div className="bg-red-50 text-red-700 p-4 rounded-md">
                    {error}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Response Section */}
          <Card>
            <CardHeader>
              <CardTitle>Response</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center h-40">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#5e65de]"></div>
                </div>
              ) : response ? (
                <div className="space-y-4">
                  <div className="bg-gray-50 p-4 rounded-md overflow-auto max-h-[500px]">
                    <pre className="text-sm whitespace-pre-wrap break-words">
                      {JSON.stringify(response, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  Submit the form to see the API response
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
} 