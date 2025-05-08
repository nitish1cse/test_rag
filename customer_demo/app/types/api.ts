export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export interface ApiHeader {
  key: string;
  value: string;
  isRequired: boolean;
}

export type ParameterType = 'string' | 'number' | 'boolean' | 'object';
export type ParameterLocation = 'path' | 'query' | 'body';

export interface ApiParameter {
  name: string;
  type: ParameterType;
  location: ParameterLocation;
  isRequired: boolean;
  defaultValue?: string;
  description?: string;
}

export interface ApiResponseMapping {
  sourceField: string;  // Field from the response of the first API
  targetParameter: string;  // Parameter name in the second API
}

export interface WorkflowStep {
  apiConfigId: string;
  order: number;
  waitTime?: number;  // Time to wait before making the next API call (in milliseconds)
  responseMapping?: ApiResponseMapping[];  // How to map response from previous step to this step's parameters
}

export interface ApiWorkflow {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  createdAt: string;
  updatedAt: string;
}

export interface ApiConfig {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  method: HttpMethod;
  headers: ApiHeader[];
  parameters: ApiParameter[];
  createdAt: string;
  updatedAt: string;
  isWorkflowEnabled?: boolean;  // Indicates if this API can be part of a workflow
  responseFields?: string[];  // Fields that can be mapped to next API call
  isPartOfWorkflow?: boolean;  // Indicates if this API is currently used in any workflow
}
