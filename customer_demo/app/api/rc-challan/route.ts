import { NextResponse } from "next/server";

// Simulated vehicle database
const vehicleDatabase = [
  {
    vehicle_number: "MH02BR5544",
    owner_name: "Rahul Kumar",
    vehicle_class: "LMV",
    registration_date: "2020-06-15",
    insurance_valid_till: "2024-06-14",
    fitness_valid_till: "2025-06-14",
    pending_challans: [
      {
        challan_number: "MH20230001",
        violation_date: "2023-12-15",
        violation_type: "Speeding",
        amount: 1000,
        status: "UNPAID"
      }
    ]
  },
  {
    vehicle_number: "DL01AB1234",
    owner_name: "Priya Singh",
    vehicle_class: "MCWG",
    registration_date: "2021-03-20",
    insurance_valid_till: "2024-03-19",
    fitness_valid_till: "2026-03-19",
    pending_challans: []
  }
];

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const vehicleNumber = searchParams.get('vehicle_number');

    // Validate required parameter
    if (!vehicleNumber) {
      return NextResponse.json(
        { error: "Vehicle number is required" },
        { status: 400 }
      );
    }

    // Validate vehicle number format (basic validation)
    const vehicleRegex = /^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$/;
    if (!vehicleRegex.test(vehicleNumber)) {
      return NextResponse.json(
        { error: "Invalid vehicle number format" },
        { status: 400 }
      );
    }

    // Simulate API processing delay
    await new Promise((resolve) => setTimeout(resolve, 800));

    // Find vehicle details
    const vehicle = vehicleDatabase.find(
      (v) => v.vehicle_number === vehicleNumber
    );

    if (!vehicle) {
      return NextResponse.json(
        { error: "Vehicle not found" },
        { status: 404 }
      );
    }

    // Calculate total pending amount
    const totalPendingAmount = vehicle.pending_challans.reduce(
      (sum, challan) => sum + challan.amount,
      0
    );

    return NextResponse.json({
      status: "success",
      data: {
        vehicle_details: {
          vehicle_number: vehicle.vehicle_number,
          owner_name: vehicle.owner_name,
          vehicle_class: vehicle.vehicle_class,
          registration_date: vehicle.registration_date,
        },
        compliance_status: {
          insurance_valid_till: vehicle.insurance_valid_till,
          fitness_valid_till: vehicle.fitness_valid_till,
          insurance_status: new Date(vehicle.insurance_valid_till) > new Date() ? "VALID" : "EXPIRED",
          fitness_status: new Date(vehicle.fitness_valid_till) > new Date() ? "VALID" : "EXPIRED"
        },
        challan_summary: {
          total_pending_challans: vehicle.pending_challans.length,
          total_pending_amount: totalPendingAmount,
          challans: vehicle.pending_challans
        },
        verification_timestamp: new Date().toISOString()
      }
    });

  } catch (error) {
    console.error('RC Challan API error:', error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
} 