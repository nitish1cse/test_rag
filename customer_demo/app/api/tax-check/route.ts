import { NextResponse } from "next/server";

// Simulated database of tax defaulters
const taxDefaulters = [
  { pan: "ABCDE1234F", company_name: "Default Corp Ltd" },
  { pan: "PQRST5678G", company_name: "Defaulter Industries" },
];

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { pan, company_name } = body;

    // Validate required fields
    if (!pan || !company_name) {
      return NextResponse.json(
        { error: "PAN and Company Name are required" },
        { status: 400 }
      );
    }

    // Validate PAN format (basic validation)
    const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
    if (!panRegex.test(pan)) {
      return NextResponse.json(
        { error: "Invalid PAN format" },
        { status: 400 }
      );
    }

    // Simulate API processing delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Check if company is a defaulter
    const isDefaulter = taxDefaulters.some(
      (d) => d.pan === pan || d.company_name.toLowerCase() === company_name.toLowerCase()
    );

    return NextResponse.json({
      status: "success",
      data: {
        pan,
        company_name,
        is_defaulter: isDefaulter,
        verification_date: new Date().toISOString(),
        risk_score: isDefaulter ? 'HIGH' : 'LOW',
        compliance_status: isDefaulter ? 'NON-COMPLIANT' : 'COMPLIANT',
        last_filing_date: isDefaulter ? '2022-04-15' : '2024-01-15',
      }
    });

  } catch (error) {
    console.error('Tax check API error:', error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
} 