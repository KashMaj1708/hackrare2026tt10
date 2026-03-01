import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import Papa from "papaparse";

const DATA_DIR = path.join(process.cwd(), "..", "dis_data");

const NUMERIC_KEYS = new Set([
  "Rank",
  "score",
  "shared_targets",
  "pathway_jaccard",
  "evidence_score",
]);

function stripNumeric(row: Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(row)) {
    if (!NUMERIC_KEYS.has(key)) {
      result[key] = value;
    }
  }
  return result;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const name = searchParams.get("name");

  if (!name) {
    return NextResponse.json({ error: "Missing disease name" }, { status: 400 });
  }

  const filename = name.replace(/ /g, "_") + ".csv";
  const csvPath = path.join(DATA_DIR, filename);

  if (!fs.existsSync(csvPath)) {
    return NextResponse.json({ error: `No data found for "${name}"` }, { status: 404 });
  }

  try {
    const csvContent = fs.readFileSync(csvPath, "utf-8");
    const parsed = Papa.parse<Record<string, string>>(csvContent, {
      header: true,
      skipEmptyLines: true,
    });

    const known = parsed.data
      .filter((row) => row.category === "KNOWN")
      .map(stripNumeric);

    const repurposing = parsed.data
      .filter((row) => row.category === "REPURPOSING")
      .map(stripNumeric);

    return NextResponse.json({ disease: name, known, repurposing });
  } catch (error) {
    console.error("Error parsing CSV:", error);
    return NextResponse.json({ error: "Failed to parse data" }, { status: 500 });
  }
}
