"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { signOut } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Search, LogOut, Plus, Edit, Trash2, GitBranch } from 'lucide-react';
import { SetuLogo } from "../../components/ui/setu-logo";
import { ApiConfig, ApiWorkflow } from "../../types/api";

export default function Dashboard() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState("");
  const [apis, setApis] = useState<ApiConfig[]>([]);
  const [workflows, setWorkflows] = useState<ApiWorkflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch APIs from the database
        const response = await fetch('/api/api-configs');
        if (!response.ok) {
          throw new Error('Failed to fetch API configurations');
        }
        const data = await response.json();
        setApis(data);

        // Load workflows from localStorage (or you can create a similar database setup for workflows)
        const savedWorkflows = JSON.parse(localStorage.getItem('apiWorkflows') || '[]');
        setWorkflows(savedWorkflows);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const filteredApis = apis.filter(api => 
    !api.isPartOfWorkflow && (
      api.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      api.description.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  const filteredWorkflows = workflows.filter(workflow => 
    workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleApiClick = (apiId: string) => {
    router.push(`/api-test/${apiId}`);
  };

  const handleWorkflowClick = (workflowId: string) => {
    router.push(`/workflow-test/${workflowId}`);
  };

  const handleEditApi = (e: React.MouseEvent, apiId: string) => {
    e.stopPropagation();
    router.push(`/api-config/${apiId}`);
  };

  const handleDeleteApi = async (e: React.MouseEvent, apiId: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this API?')) {
      try {
        const response = await fetch(`/api/api-configs/${apiId}`, {
          method: 'DELETE',
        });

        if (!response.ok) {
          throw new Error('Failed to delete API configuration');
        }

        setApis(apis.filter(api => api.id !== apiId));
      } catch (error) {
        console.error('Error deleting API:', error);
      }
    }
  };

  const handleDeleteWorkflow = (e: React.MouseEvent, workflowId: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this workflow?')) {
      const updatedWorkflows = workflows.filter(w => w.id !== workflowId);
      localStorage.setItem('apiWorkflows', JSON.stringify(updatedWorkflows));
      setWorkflows(updatedWorkflows);
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
          <div className="flex items-center space-x-4">
            <Button
              onClick={() => router.push('/workflow')}
              className="bg-[#5e65de] hover:bg-[#4a51c4]"
            >
              <GitBranch className="w-4 h-4 mr-2" />
              Create Workflow
            </Button>
            <Button
              onClick={() => router.push('/api-config')}
              className="bg-[#5e65de] hover:bg-[#4a51c4]"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add New API
            </Button>
            <Button
              variant="outline"
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="border-gray-200 text-gray-700 hover:bg-gray-50"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8">
        <div className="flex flex-col space-y-8">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">API Demo Dashboard</h1>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <Input
              type="search"
              placeholder="Search APIs and workflows..."
              className="pl-10 bg-white border-gray-200 text-gray-900 placeholder:text-gray-400 max-w-md"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* Workflows Section */}
          {filteredWorkflows.length > 0 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Workflows</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredWorkflows.map((workflow) => (
                  <Card
                    key={workflow.id}
                    className="cursor-pointer transition-all relative group bg-gradient-to-br from-blue-50 via-white to-blue-50 border border-blue-100 hover:border-blue-200 hover:shadow-lg"
                    onClick={() => handleWorkflowClick(workflow.id)}
                  >
                    <CardHeader>
                      <div className="flex items-center space-x-2">
                        <GitBranch className="w-5 h-5 text-blue-600" />
                        <CardTitle className="text-gray-900">{workflow.name}</CardTitle>
                      </div>
                      <CardDescription className="text-gray-500">{workflow.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <p className="text-sm text-gray-500">{workflow.steps.length} steps</p>
                      </div>
                    </CardContent>
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={(e) => handleDeleteWorkflow(e, workflow.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* APIs Section */}
          {filteredApis.length > 0 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">APIs</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredApis.map((api) => (
                  <Card
                    key={api.id}
                    className="cursor-pointer transition-all relative group bg-gradient-to-br from-gray-100 via-white to-gray-200 border border-gray-200/50 shadow-lg hover:shadow-xl backdrop-blur-sm hover:scale-[1.02] overflow-hidden"
                    onClick={() => handleApiClick(api.id)}
                    style={{
                      background: 'linear-gradient(145deg, #ffffff 0%, #f3f4f6 100%)',
                    }}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent pointer-events-none" />
                    <CardHeader>
                      <CardTitle className="text-gray-900 font-bold">{api.name}</CardTitle>
                      <CardDescription className="text-gray-600">{api.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <p className="text-sm text-gray-500 truncate">{api.endpoint}</p>
                      </div>
                    </CardContent>
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0 bg-white/80 backdrop-blur-sm border-gray-200/50 hover:bg-white"
                        onClick={(e) => handleEditApi(e, api.id)}
                      >
                        <Edit className="h-4 w-4 text-blue-600" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0 bg-white/80 backdrop-blur-sm border-gray-200/50 hover:bg-white"
                        onClick={(e) => handleDeleteApi(e, api.id)}
                      >
                        <Trash2 className="h-4 w-4 text-red-600" />
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {filteredApis.length === 0 && filteredWorkflows.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">No APIs or workflows found.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
} 