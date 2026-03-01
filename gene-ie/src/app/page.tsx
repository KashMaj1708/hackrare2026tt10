"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Search,
  FlaskConical,
  ChevronDown,
  ChevronUp,
  Dna,
  Pill,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Loader2,
  Sparkles,
  Hash,
  Activity,
  AlertTriangle,
} from "lucide-react";

interface DrugRow {
  drug: string;
  disease: string;
  category: string;
  verdict: string;
  drug_targets: string;
  disease_pathway_genes: string;
  evidence_tier: string;
  uncertainty: string;
  gemini_reasoning: string;
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const v = verdict?.toUpperCase() || "";
  if (v === "CANDIDATE")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[#7c5cfc]/15 px-2.5 py-0.5 text-xs font-semibold text-[#a78bfa]">
        <ShieldCheck size={12} /> Candidate
      </span>
    );
  if (v === "UNLIKELY")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[#fbbf24]/15 px-2.5 py-0.5 text-xs font-semibold text-[#fbbf24]">
        <ShieldAlert size={12} /> Unlikely
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#f87171]/15 px-2.5 py-0.5 text-xs font-semibold text-[#f87171]">
      <ShieldX size={12} /> Reject
    </span>
  );
}

function DrugCard({
  row,
  rank,
  isRepurposing,
}: {
  row: DrugRow;
  rank: number;
  isRepurposing: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="group rounded-xl border border-[#1e1e2a] bg-[#111118] hover:border-[#2a2a3a] transition-all duration-200">
      {/* Main row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-5 py-4 flex items-center gap-4 cursor-pointer"
      >
        {/* Rank */}
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-[#1a1a24] flex items-center justify-center">
          <span className="text-sm font-bold text-[#6b6b80]">
            {rank}
          </span>
        </div>

        {/* Drug name + verdict */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <Pill size={14} className="text-[#7c5cfc] flex-shrink-0" />
            <span className="font-semibold text-[#e8e8ed] truncate">
              {row.drug}
            </span>
            <VerdictBadge verdict={row.verdict} />
            {isRepurposing && (
              <span className="text-[10px] uppercase tracking-wider font-bold text-[#7c5cfc]/60 bg-[#7c5cfc]/8 px-1.5 py-0.5 rounded">
                Repurposed
              </span>
            )}
          </div>
        </div>

        {/* Evidence + Uncertainty pills */}
        <div className="flex-shrink-0 hidden sm:flex items-center gap-3">
          {row.evidence_tier && (
            <span className="text-xs text-[#6b6b80] bg-[#1a1a24] px-2 py-0.5 rounded capitalize">
              {row.evidence_tier}
            </span>
          )}
          {row.uncertainty && (
            <span className="text-xs text-[#6b6b80] bg-[#1a1a24] px-2 py-0.5 rounded">
              {row.uncertainty}
            </span>
          )}
        </div>

        {/* Expand icon */}
        <div className="flex-shrink-0 text-[#6b6b80] group-hover:text-[#7c5cfc] transition-colors">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-5 pb-5 animate-fade-in">
          <div className="border-t border-[#1e1e2a] pt-4 space-y-4">
            {/* Info grid — non-numeric only */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="rounded-lg bg-[#0d0d14] px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-wider text-[#6b6b80] mb-1">
                  Category
                </div>
                <div className="text-sm font-semibold text-[#e8e8ed]">
                  {row.category || "N/A"}
                </div>
              </div>
              <div className="rounded-lg bg-[#0d0d14] px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-wider text-[#6b6b80] mb-1">
                  Evidence Tier
                </div>
                <div className="text-sm font-semibold text-[#e8e8ed] capitalize">
                  {row.evidence_tier || "N/A"}
                </div>
              </div>
              <div className="rounded-lg bg-[#0d0d14] px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-wider text-[#6b6b80] mb-1">
                  Uncertainty
                </div>
                <div className="text-sm font-semibold text-[#e8e8ed]">
                  {row.uncertainty || "N/A"}
                </div>
              </div>
            </div>

            {/* Gene targets */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-[#6b6b80]">
                <Dna size={12} />
                <span className="uppercase tracking-wider font-semibold">
                  Drug Targets
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(row.drug_targets || "none").split(",").map((gene, i) => (
                  <span
                    key={i}
                    className="rounded bg-[#7c5cfc]/10 px-2 py-0.5 text-xs font-mono text-[#a78bfa]"
                  >
                    {gene.trim()}
                  </span>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-[#6b6b80]">
                <Activity size={12} />
                <span className="uppercase tracking-wider font-semibold">
                  Disease Pathway Genes
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(row.disease_pathway_genes || "none")
                  .split(",")
                  .map((gene, i) => (
                    <span
                      key={i}
                      className="rounded bg-[#34d399]/10 px-2 py-0.5 text-xs font-mono text-[#34d399]"
                    >
                      {gene.trim()}
                    </span>
                  ))}
              </div>
            </div>

            {/* Gemini reasoning */}
            {row.gemini_reasoning && (
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-xs text-[#6b6b80]">
                  <Sparkles size={12} className="text-[#fbbf24]" />
                  <span className="uppercase tracking-wider font-semibold">
                    Gemini Reasoning
                  </span>
                </div>
                <div className="rounded-lg bg-[#0d0d14] border border-[#1e1e2a] p-4 text-sm leading-relaxed text-[#b0b0c0]">
                  {row.gemini_reasoning}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [diseases, setDiseases] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [drugCount, setDrugCount] = useState(10);
  const [loading, setLoading] = useState(false);
  const [knownDrugs, setKnownDrugs] = useState<DrugRow[]>([]);
  const [repurposingDrugs, setRepurposingDrugs] = useState<DrugRow[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available diseases on mount
  useEffect(() => {
    fetch("/api/diseases")
      .then((r) => r.json())
      .then((data) => setDiseases(data.diseases || []))
      .catch(() => setDiseases([]));
  }, []);

  const filteredDiseases = diseases.filter((d) =>
    d.toLowerCase().includes(query.toLowerCase())
  );

  const handleSearch = useCallback(
    async (diseaseName: string) => {
      setLoading(true);
      setError(null);
      setSelectedDisease(diseaseName);
      setShowSuggestions(false);

      try {
        const res = await fetch(
          `/api/disease?name=${encodeURIComponent(diseaseName)}`
        );
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || "Failed to fetch data");
        }
        const data = await res.json();
        setKnownDrugs(data.known || []);
        setRepurposingDrugs(data.repurposing || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setKnownDrugs([]);
        setRepurposingDrugs([]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const displayedKnown = knownDrugs.slice(0, drugCount);
  const displayedRepurposing = repurposingDrugs.slice(0, drugCount);
  const totalResults = knownDrugs.length + repurposingDrugs.length;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-[#1e1e2a] bg-[#0a0a0f]/80 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <FlaskConical size={24} className="text-[#7c5cfc] logo-glow" />
          <h1 className="text-xl font-bold tracking-tight">
            <span className="text-[#7c5cfc]">Gene</span>
            <span className="text-[#e8e8ed]">-ie</span>
          </h1>
          <span className="text-[10px] uppercase tracking-widest text-[#6b6b80] ml-1 hidden sm:inline">
            Rare Disease Drug Repurposing
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* Hero / Search Section */}
        <div className="text-center mb-10">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-3">
            <span className="text-[#e8e8ed]">Discover </span>
            <span className="text-[#7c5cfc]">Drug Repurposing</span>
            <span className="text-[#e8e8ed]"> Candidates</span>
          </h2>
          <p className="text-[#6b6b80] text-base max-w-lg mx-auto">
            Search a rare disease to see AI-ranked drug candidates with
            Gemini-powered biological reasoning.
          </p>
        </div>

        {/* Search bar */}
        <div className="max-w-2xl mx-auto mb-10 space-y-4">
          <div className="relative">
            <div className="flex items-center gap-3 rounded-xl border border-[#1e1e2a] bg-[#111118] px-4 py-3 focus-within:border-[#7c5cfc] focus-within:shadow-[0_0_0_1px_rgba(124,92,252,0.3)] transition-all">
              <Search size={18} className="text-[#6b6b80] flex-shrink-0" />
              <input
                type="text"
                placeholder="Enter disease name (e.g. Duchenne muscular dystrophy)"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && filteredDiseases.length > 0) {
                    handleSearch(filteredDiseases[0]);
                    setQuery(filteredDiseases[0]);
                  }
                }}
                className="flex-1 bg-transparent text-[#e8e8ed] placeholder-[#4a4a5a] outline-none text-sm"
              />
              {loading && (
                <Loader2
                  size={18}
                  className="text-[#7c5cfc] animate-spin flex-shrink-0"
                />
              )}
            </div>

            {/* Suggestions dropdown */}
            {showSuggestions && query.length > 0 && filteredDiseases.length > 0 && (
              <div className="absolute z-40 mt-2 w-full rounded-xl border border-[#1e1e2a] bg-[#111118] shadow-2xl overflow-hidden">
                {filteredDiseases.slice(0, 8).map((d) => (
                  <button
                    key={d}
                    onClick={() => {
                      setQuery(d);
                      handleSearch(d);
                    }}
                    className="w-full text-left px-4 py-3 text-sm text-[#b0b0c0] hover:bg-[#7c5cfc]/10 hover:text-[#e8e8ed] transition-colors cursor-pointer flex items-center gap-2"
                  >
                    <Dna size={14} className="text-[#7c5cfc] flex-shrink-0" />
                    {d}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Drug count selector */}
          <div className="flex items-center justify-center gap-4">
            <div className="flex items-center gap-2 text-sm text-[#6b6b80]">
              <Hash size={14} />
              <span>Results per section:</span>
            </div>
            <div className="flex gap-1.5">
              {[5, 10, 20, 50].map((n) => (
                <button
                  key={n}
                  onClick={() => setDrugCount(n)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    drugCount === n
                      ? "bg-[#7c5cfc] text-white"
                      : "bg-[#1a1a24] text-[#6b6b80] hover:text-[#e8e8ed] hover:bg-[#222230]"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="max-w-2xl mx-auto mb-8 rounded-xl border border-[#f87171]/30 bg-[#f87171]/10 px-5 py-4 flex items-center gap-3 animate-fade-in">
            <AlertTriangle size={18} className="text-[#f87171] flex-shrink-0" />
            <p className="text-sm text-[#f87171]">{error}</p>
          </div>
        )}

        {/* Results */}
        {selectedDisease && !loading && !error && (
          <div className="animate-fade-in space-y-10">
            {/* Summary */}
            <div className="text-center">
              <p className="text-[#6b6b80] text-sm">
                Showing results for{" "}
                <span className="font-semibold text-[#e8e8ed]">
                  {selectedDisease}
                </span>{" "}
                &mdash; {totalResults} drugs evaluated
              </p>
            </div>

            {/* Section A: Known Treatments */}
            {displayedKnown.length > 0 && (
              <section>
                <div className="flex items-center gap-2.5 mb-4">
                  <div className="h-5 w-1 rounded-full bg-[#34d399]" />
                  <h3 className="text-lg font-bold text-[#e8e8ed]">
                    Known Treatments
                  </h3>
                  <span className="text-xs text-[#6b6b80] bg-[#1a1a24] px-2 py-0.5 rounded-full">
                    {knownDrugs.length} drugs
                  </span>
                </div>
                <p className="text-xs text-[#6b6b80] mb-4 ml-3.5">
                  Drugs already indicated for this disease
                </p>
                <div className="space-y-2 stagger-children">
                  {displayedKnown.map((row, i) => (
                    <DrugCard
                      key={row.drug}
                      row={row}
                      rank={i + 1}
                      isRepurposing={false}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Section B: Repurposing Candidates */}
            {displayedRepurposing.length > 0 && (
              <section>
                <div className="flex items-center gap-2.5 mb-4">
                  <div className="h-5 w-1 rounded-full bg-[#7c5cfc]" />
                  <h3 className="text-lg font-bold text-[#e8e8ed]">
                    Repurposing Candidates
                  </h3>
                  <span className="text-xs text-[#6b6b80] bg-[#1a1a24] px-2 py-0.5 rounded-full">
                    {repurposingDrugs.length} drugs
                  </span>
                </div>
                <p className="text-xs text-[#6b6b80] mb-4 ml-3.5">
                  Drugs indicated for other diseases — novel repurposing
                  candidates
                </p>
                <div className="space-y-2 stagger-children">
                  {displayedRepurposing.map((row, i) => (
                    <DrugCard
                      key={row.drug}
                      row={row}
                      rank={i + 1}
                      isRepurposing={true}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Empty state */}
            {totalResults === 0 && (
              <div className="text-center py-16">
                <FlaskConical
                  size={48}
                  className="mx-auto mb-4 text-[#2a2a3a]"
                />
                <p className="text-[#6b6b80]">
                  No results found for this disease.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Empty initial state */}
        {!selectedDisease && !loading && (
          <div className="text-center py-20">
            <FlaskConical
              size={56}
              className="mx-auto mb-5 text-[#1e1e2a]"
            />
            <p className="text-[#4a4a5a] text-sm">
              Search for a disease above to explore drug repurposing candidates.
            </p>
            {diseases.length > 0 && (
              <div className="mt-6">
                <p className="text-[10px] uppercase tracking-wider text-[#4a4a5a] mb-3">
                  Available diseases
                </p>
                <div className="flex flex-wrap justify-center gap-2 max-w-xl mx-auto">
                  {diseases.map((d) => (
                    <button
                      key={d}
                      onClick={() => {
                        setQuery(d);
                        handleSearch(d);
                      }}
                      className="rounded-full border border-[#1e1e2a] bg-[#111118] px-3 py-1.5 text-xs text-[#6b6b80] hover:border-[#7c5cfc] hover:text-[#a78bfa] transition-all cursor-pointer"
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#1e1e2a] mt-20">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-[#4a4a5a]">
          <span>Gene-ie &mdash; HackRare 2026</span>
          <span>Powered by Llama 3.1 + Gemini</span>
        </div>
      </footer>
    </div>
  );
}
