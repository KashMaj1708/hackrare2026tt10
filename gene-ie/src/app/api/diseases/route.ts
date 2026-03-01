import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "..", "dis_data");

export async function GET() {
  try {
    if (!fs.existsSync(DATA_DIR)) {
      return NextResponse.json({ diseases: [] });
    }

    const files = fs.readdirSync(DATA_DIR).filter((f) => f.endsWith(".csv"));
    const diseases = files.map((f) => {
      const stem = f.replace(/\.csv$/, "");
      return stem.replace(/_/g, " ");
    });

    return NextResponse.json({ diseases });
  } catch (error) {
    console.error("Error reading data directory:", error);
    return NextResponse.json({ diseases: [] }, { status: 500 });
  }
}
