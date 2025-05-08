import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { endpoint, method, headers, data } = body;

    // Prepare request options
    const requestOptions: RequestInit = {
      method: method,
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
      ...(method !== 'GET' && { body: JSON.stringify(data) })
    };

    console.log('Proxy request:', {
      endpoint,
      method,
      headers,
      data
    });

    // Make the actual API call
    const response = await fetch(endpoint, requestOptions);
    const responseData = await response.json();

    // Return the response with the same status
    return NextResponse.json(responseData, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to make API request' },
      { status: 500 }
    );
  }
} 