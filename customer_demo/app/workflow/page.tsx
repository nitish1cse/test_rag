"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { SetuLogo } from "../../components/ui/setu-logo";
import { ApiConfig, ApiWorkflow, WorkflowStep, ApiResponseMapping } from "../../types/api";
import { ArrowLeft, Plus, ArrowDown, X } from 'lucide-react';

export default function WorkflowPage() {
  const router = useRouter();
  const [apis, setApis] = useState<ApiConfig[]>([]);
  const [workflow, setWorkflow] = useState<Partial<ApiWorkflow>>({
    name: '',
    description: '',
    steps: []
  });

  useEffect(() => {
    const savedApis = JSON.parse(localStorage.getItem('apiConfigs') || '[]');
    const savedWorkflows = JSON.parse(localStorage.getItem('apiWorkflows') || '[]');

    // Mark APIs that are used in workflows
    const updatedApis = savedApis.map(api => ({
      ...api,
      isPartOfWorkflow: savedWorkflows.some(workflow => 
        workflow.steps.some(step => step.apiConfigId === api.id)
      )
    }));

    setApis(updatedApis);
  }, []);

  const handleAddStep = () => {
    setWorkflow(prev => ({
      ...prev,
      steps: [...(prev.steps || []), {
        apiConfigId: '',
        order: (prev.steps?.length || 0) + 1,
        responseMapping: []
      }]
    }));
  };

  const handleRemoveStep = (index: number) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps?.filter((_, i) => i !== index)
    }));
  };

  const handleStepChange = (index: number, apiConfigId: string) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps?.map((step, i) => 
        i === index ? { ...step, apiConfigId, responseMapping: [] } : step
      )
    }));
  };

  const handleMappingChange = (stepIndex: number, mappingIndex: number, field: keyof ApiResponseMapping, value: string) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps?.map((step, i) => {
        if (i !== stepIndex) return step;
        return {
          ...step,
          responseMapping: step.responseMapping?.map((mapping, j) => 
            j === mappingIndex ? { ...mapping, [field]: value } : mapping
          )
        };
      })
    }));
  };

  const handleAddMapping = (stepIndex: number) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps?.map((step, i) => {
        if (i !== stepIndex) return step;
        return {
          ...step,
          responseMapping: [...(step.responseMapping || []), { sourceField: '', targetParameter: '' }]
        };
      })
    }));
  };

  const handleRemoveMapping = (stepIndex: number, mappingIndex: number) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps?.map((step, i) => {
        if (i !== stepIndex) return step;
        return {
          ...step,
          responseMapping: step.responseMapping?.filter((_, j) => j !== mappingIndex)
        };
      })
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newWorkflow: ApiWorkflow = {
      ...workflow as ApiWorkflow,
      id: Date.now().toString(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    const existingWorkflows = JSON.parse(localStorage.getItem('apiWorkflows') || '[]');
    localStorage.setItem('apiWorkflows', JSON.stringify([...existingWorkflows, newWorkflow]));
    router.push('/dashboard');
  };

  const handleBackToDashboard = () => {
    try {
      router.push('/dashboard');
    } catch (error) {
      console.error('Navigation error:', error);
      window.location.href = '/dashboard';
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
          <Link href="/dashboard" passHref>
            <Button
              variant="outline"
              onClick={handleBackToDashboard}
              className="border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Dashboard
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Create API Workflow</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Label>Workflow Name</Label>
                  <Input
                    value={workflow.name}
                    onChange={e => setWorkflow(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Aadhaar Verification Flow"
                    required
                  />
                </div>

                <div>
                  <Label>Description</Label>
                  <Input
                    value={workflow.description}
                    onChange={e => setWorkflow(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Workflow for Aadhaar verification process"
                    required
                  />
                </div>

                <div className="space-y-4">
                  <Label>Workflow Steps</Label>
                  {workflow.steps?.map((step, stepIndex) => (
                    <div key={stepIndex} className="border rounded-lg p-4 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium">Step {step.order}</h3>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveStep(stepIndex)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>

                      <div>
                        <Label>Select API</Label>
                        <select
                          value={step.apiConfigId}
                          onChange={e => handleStepChange(stepIndex, e.target.value)}
                          className="w-full p-2 border rounded-md"
                          required
                        >
                          <option value="">Select an API</option>
                          {apis.map(api => (
                            <option 
                              key={api.id} 
                              value={api.id}
                              disabled={api.isPartOfWorkflow && !workflow.steps?.some(s => s.apiConfigId === api.id)}
                            >
                              {api.name} {api.isPartOfWorkflow ? '(Used in another workflow)' : ''}
                            </option>
                          ))}
                        </select>
                      </div>

                      {stepIndex > 0 && (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label>Response Mappings</Label>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => handleAddMapping(stepIndex)}
                            >
                              <Plus className="w-4 h-4 mr-2" />
                              Add Mapping
                            </Button>
                          </div>
                          {step.responseMapping?.map((mapping, mappingIndex) => (
                            <div key={mappingIndex} className="flex items-center space-x-2">
                              <Input
                                value={mapping.sourceField}
                                onChange={e => handleMappingChange(stepIndex, mappingIndex, 'sourceField', e.target.value)}
                                placeholder="Response field path"
                                className="flex-1"
                              />
                              <ArrowDown className="w-4 h-4 text-gray-400" />
                              <Input
                                value={mapping.targetParameter}
                                onChange={e => handleMappingChange(stepIndex, mappingIndex, 'targetParameter', e.target.value)}
                                placeholder="Target parameter"
                                className="flex-1"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveMapping(stepIndex, mappingIndex)}
                                className="text-red-600 hover:text-red-700"
                              >
                                <X className="w-4 h-4" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}

                      {stepIndex < (workflow.steps?.length || 0) - 1 && (
                        <div className="flex items-center justify-center py-2">
                          <ArrowDown className="w-6 h-6 text-gray-400" />
                        </div>
                      )}
                    </div>
                  ))}

                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleAddStep}
                    className="w-full"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Step
                  </Button>
                </div>
              </div>

              <Button type="submit" className="w-full">
                Create Workflow
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
} 