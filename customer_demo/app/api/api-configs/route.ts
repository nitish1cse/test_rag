import { NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, description, endpoint, method, headers, parameters, isWorkflowEnabled } = body;

    // Validate required fields
    if (!name || !description || !endpoint || !method) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    const apiConfig = await prisma.apiConfig.create({
      data: {
        name,
        description,
        endpoint,
        method,
        isWorkflowEnabled: isWorkflowEnabled || false,
        headers: {
          create: headers?.map((header: any) => ({
            key: header.key,
            value: header.value,
            isRequired: header.isRequired || false
          })) || []
        },
        parameters: {
          create: parameters?.map((param: any) => ({
            name: param.name,
            type: param.type,
            location: param.location,
            isRequired: param.isRequired || false,
            defaultValue: param.defaultValue,
            description: param.description
          })) || []
        }
      },
      include: {
        headers: true,
        parameters: true
      }
    });

    return NextResponse.json(apiConfig);
  } catch (error) {
    console.error('Error creating API config:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to create API configuration' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const apiConfigs = await prisma.apiConfig.findMany({
      include: {
        headers: true,
        parameters: true
      }
    });
    return NextResponse.json(apiConfigs);
  } catch (error) {
    console.error('Error fetching API configs:', error);
    return NextResponse.json(
      { error: 'Failed to fetch API configurations' },
      { status: 500 }
    );
  }
} 