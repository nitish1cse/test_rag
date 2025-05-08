import { NextResponse } from 'next/server';
import prisma from '../../../../lib/prisma';

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const apiConfig = await prisma.apiConfig.delete({
      where: {
        id: params.id
      }
    });

    return NextResponse.json(apiConfig);
  } catch (error) {
    console.error('Error deleting API config:', error);
    return NextResponse.json(
      { error: 'Failed to delete API configuration' },
      { status: 500 }
    );
  }
}

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  console.log('Fetching API config with ID:', params.id);
  
  try {
    const apiConfig = await prisma.apiConfig.findUnique({
      where: {
        id: params.id
      },
      include: {
        headers: true,
        parameters: true
      }
    });

    console.log('API config found:', apiConfig ? 'yes' : 'no');

    if (!apiConfig) {
      console.log('API config not found for ID:', params.id);
      return NextResponse.json(
        { error: 'API configuration not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(apiConfig);
  } catch (error) {
    console.error('Detailed error fetching API config:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch API configuration' },
      { status: 500 }
    );
  }
} 