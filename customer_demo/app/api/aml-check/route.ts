import { NextResponse } from "next/server";

// Simulated database of high-risk individuals
const highRiskIndividuals = [
  { name: "John Smith", date_of_birth: "1980-05-15" },
  { name: "Alice Johnson", date_of_birth: "1975-12-20" },
];

// Simulated PEP database
const pepDatabase = [
  { name: "Robert Wilson", date_of_birth: "1968-03-10", position: "Former Minister" },
];

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, date_of_birth } = body;

    // Validate required fields
    if (!name || !date_of_birth) {
      return NextResponse.json(
        { error: "Name and Date of Birth are required" },
        { status: 400 }
      );
    }

    // Validate date format
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(date_of_birth)) {
      return NextResponse.json(
        { error: "Invalid date format. Use YYYY-MM-DD" },
        { status: 400 }
      );
    }

    // Simulate API processing delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Check various lists
    const isHighRisk = highRiskIndividuals.some(
      (person) => 
        person.name.toLowerCase() === name.toLowerCase() &&
        person.date_of_birth === date_of_birth
    );

    const pepMatch = pepDatabase.find(
      (person) =>
        person.name.toLowerCase() === name.toLowerCase() &&
        person.date_of_birth === date_of_birth
    );

    // Generate random values for demonstration
    const mediaMatches = Math.random() > 0.8 ? [
      {
        source: "Global News Daily",
        date: "2023-12-10",
        headline: "Business Investigation Report",
      }
    ] : [];

    return NextResponse.json({
      status: "success",
      data: {
        name,
        date_of_birth,
        screening_date: new Date().toISOString(),
        risk_indicators: {
          sanctions_match: isHighRisk,
          pep_status: pepMatch ? {
            is_pep: true,
            position: pepMatch.position,
            risk_level: "HIGH"
          } : {
            is_pep: false,
            risk_level: "LOW"
          },
          adverse_media: {
            found: mediaMatches.length > 0,
            matches: mediaMatches
          }
        },
        overall_risk_score: isHighRisk || pepMatch ? "HIGH" : "LOW",
        recommendation: isHighRisk || pepMatch 
          ? "Enhanced Due Diligence Required"
          : "Standard Due Diligence Sufficient",
      }
    });

  } catch (error) {
    console.error('AML check API error:', error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
} 