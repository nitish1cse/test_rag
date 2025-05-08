"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { SetuLogo } from "../../../components/ui/setu-logo";
import { ApiConfig, ApiWorkflow } from "../../../types/api";
import { ArrowLeft, ArrowRight } from 'lucide-react';

interface Props {
  params: {
    id: string;
  };
}

export default function WorkflowTestPage({ params }: Props) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<ApiWorkflow | null>(null);
  const [apis, setApis] = useState<ApiConfig[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepResponses, setStepResponses] = useState<Record<number, any>>({});
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load workflow and APIs
    const workflows = JSON.parse(localStorage.getItem('apiWorkflows') || '[]');
    const workflow = workflows.find((w: ApiWorkflow) => w.id === params.id);
    const apis = JSON.parse(localStorage.getItem('apiConfigs') || '[]');
    
    if (workflow) {
      setWorkflow(workflow);
      setApis(apis);
    } else {
      router.push('/dashboard');
    }
  }, [params.id, router]);

  const getCurrentApi = () => {
    if (!workflow || !workflow.steps[currentStep]) return null;
    return apis.find(api => api.id === workflow.steps[currentStep].apiConfigId);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workflow || !getCurrentApi()) return;

    setLoading(true);
    setError(null);

    try {
      const currentApi = getCurrentApi()!;
      const step = workflow.steps[currentStep];

      // Prepare request data by combining form data with mapped values from previous responses
      const requestData = { ...formData };
      if (step.responseMapping) {
        step.responseMapping.forEach(mapping => {
          const [prevStepIndex, field] = mapping.sourceField.split('.');
          const prevResponse = stepResponses[parseInt(prevStepIndex)];
          if (prevResponse) {
            requestData[mapping.targetParameter] = prevResponse[field];
          }
        });
      }

      // Make API request
      const response = await fetch('/api/proxy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          endpoint: currentApi.endpoint,
          method: currentApi.method,
          headers: currentApi.headers.reduce((acc, header) => ({
            ...acc,
            [header.key]: header.value
          }), {}),
          data: requestData
        })
      });

      const data = await response.json();
      
      // Store response for this step
      setStepResponses(prev => ({
        ...prev,
        [currentStep]: data
      }));

      // Move to next step if available
      if (currentStep < workflow.steps.length - 1) {
        setCurrentStep(prev => prev + 1);
        setFormData({}); // Clear form for next step
      }

    } catch (err) {
      console.error('Workflow step error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!workflow || !getCurrentApi()) {
    return <div>Loading...</div>;
  }

  const currentApi = getCurrentApi()!;

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

      <main className="max-w-7xl mx-auto px-8 py-8">
        <div className="flex flex-col space-y-4">
          <h1 className="text-2xl font-bold text-gray-900">{workflow.name}</h1>
          <p className="text-gray-500">{workflow.description}</p>
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Current Step Form */}
          <Card>
            <CardHeader>
              <CardTitle>Step {currentStep + 1}: {currentApi.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {currentApi.parameters
                  .filter(param => !param.defaultValue && !workflow.steps[currentStep].responseMapping?.some(m => m.targetParameter === param.name))
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

                {/* Show mapped parameters */}
                {workflow.steps[currentStep].responseMapping && workflow.steps[currentStep].responseMapping.length > 0 && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-md">
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Mapped Parameters</h3>
                    {workflow.steps[currentStep].responseMapping.map((mapping, index) => (
                      <div key={index} className="flex justify-between items-center text-sm text-gray-500">
                        <span>{mapping.targetParameter}</span>
                        <span className="font-mono">from Step {parseInt(mapping.sourceField.split('.')[0]) + 1}</span>
                      </div>
                    ))}
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full bg-[#5e65de] hover:bg-[#4a51c4]"
                  disabled={loading}
                >
                  {loading ? 'Processing...' : `Execute Step ${currentStep + 1}`}
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
              <CardTitle>Workflow Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(stepResponses).map(([step, response]) => (
                  <div key={step} className="border-b pb-4">
                    <h3 className="font-medium mb-2">Step {parseInt(step) + 1} Response</h3>
                    <div className="bg-gray-50 p-4 rounded-md overflow-auto max-h-[200px]">
                      <pre className="text-sm whitespace-pre-wrap break-words">
                        {JSON.stringify(response, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}

                {Object.keys(stepResponses).length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    No steps executed yet
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
} 