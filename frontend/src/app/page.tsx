"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { 
  GitBranch, 
  Search, 
  ArrowRight, 
  Database, 
  Code2, 
  Clock, 
  Trash2, 
  AlertCircle, 
  ExternalLink,
  ChevronRight,
  Loader2,
  FileCode
} from "lucide-react";

// Custom inline SVG for the GitHub Brand Logo
const GitHubIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
  </svg>
);

// API Base URL
const API_BASE = "http://localhost:8000/api";

interface RepositorySummary {
  id: number;
  name: string;
  owner: string;
  github_url: string;
  description: string | null;
  primary_language: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export default function HomePage() {
  const router = useRouter();
  const [githubUrl, setGithubUrl] = useState("");
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Ingestion status tracking
  const [activeImportRepo, setActiveImportRepo] = useState<RepositorySummary | null>(null);
  const [importLogs, setImportLogs] = useState<string[]>([]);

  // Fetch repositories list
  const fetchRepositories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/repos/`);
      if (res.ok) {
        const data = await res.json();
        setRepositories(data);
      }
    } catch (err) {
      console.error("Failed to load repositories:", err);
    }
  }, []);

  useEffect(() => {
    fetchRepositories();
  }, [fetchRepositories]);


  // Polling helper for active import
  const activeImportId = activeImportRepo?.id;  
  
useEffect(() => {  
  if (!activeImportId) return;  
  
  let intervalId: NodeJS.Timeout;  
  let stopped = false;  
  
  const pollStatus = async () => {  
    try {  
      const res = await fetch(`${API_BASE}/repos/${activeImportId}`);  
      if (!res.ok) return;  
      const data: RepositorySummary = await res.json();  
      setActiveImportRepo(data);  
  
      const logs = ["Initializing ingestion pipeline..."];  
      if (["cloning", "parsing", "indexing", "ready"].includes(data.status)) {  
        logs.push("Cloning repository into local filesystem... Done.");  
      }  
      if (["parsing", "indexing", "ready"].includes(data.status)) {  
        logs.push("Parsing file structure & extracting code components... Done.");  
      }  
      if (["indexing", "ready"].includes(data.status)) {  
        logs.push("Chunking code and generating embeddings... Done.");  
        logs.push("Indexing chunks in ChromaDB vector database... Done.");  
      }  
      if (data.status === "ready") {  
        logs.push("Generating AI repository overview... Done.");  
        logs.push("Repository is ready! Redirecting...");  
        if (!stopped) {  
          stopped = true;  
          clearInterval(intervalId);  
        }  
        setTimeout(() => router.push(`/dashboard/${data.id}`), 1500);  
      }  
      if (data.status === "failed") {  
        logs.push(`Failed: ${data.error_message || "Unknown error occurred"}`);  
        if (!stopped) {  
          stopped = true;  
          clearInterval(intervalId);  
        }  
      }  
      setImportLogs(logs);  
    } catch (err) {  
      console.error("Error polling repo status:", err);  
    }  
  };  
  
  intervalId = setInterval(pollStatus, 2000);  
  pollStatus(); // initial check  
  
  return () => clearInterval(intervalId);  
  // depend ONLY on the stable id, not the whole object  
  // eslint-disable-next-line react-hooks/exhaustive-deps  
}, [activeImportId, router]);



  // Handle repository import
  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;

    setIsLoading(true);
    setError(null);
    setImportLogs(["Submitting URL to parser..."]);

    try {
      const res = await fetch(`${API_BASE}/repos/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: githubUrl.trim() }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to start repository import");
      }

      const repo: RepositorySummary = await res.json();
      setActiveImportRepo(repo);
      setGithubUrl("");
      fetchRepositories(); // Refresh the list
    } catch (err: any) {
      setError(err.message || "An error occurred. Check backend console.");
      setIsLoading(false);
    }
  };

  // Handle repository delete
  const handleDeleteRepo = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Avoid triggering card navigation
    if (!confirm("Are you sure you want to delete this repository analysis?")) return;

    try {
      const res = await fetch(`${API_BASE}/repos/${id}`, { method: "DELETE" });
      if (res.ok) {
        setRepositories(prev => prev.filter(r => r.id !== id));
        if (activeImportRepo && activeImportRepo.id === id) {
          setActiveImportRepo(null);
          setIsLoading(false);
        }
      }
    } catch (err) {
      console.error("Failed to delete repository:", err);
    }
  };

  return (
    <div className="min-h-screen relative flex flex-col items-center px-4 py-12 md:py-24">
      {/* Decorative Blur Orbs */}
      <div className="absolute top-[10%] left-[20%] w-[350px] h-[350px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[20%] right-[10%] w-[400px] h-[400px] bg-sky-500/5 rounded-full blur-[120px] pointer-events-none" />

      {/* Header / Brand */}
      <div className="flex items-center gap-3 mb-4 text-indigo-400">
        <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
          <GitBranch className="w-8 h-8" />
        </div>
        <span className="text-2xl font-bold tracking-tight text-white code-font">GitInsight</span>
        <span className="px-2 py-0.5 text-xs font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 rounded-full">v1.0 MVP</span>
      </div>

      {/* Hero Header */}
      <div className="text-center max-w-2xl mb-12">
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-white mb-4 leading-tight bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
          Understand unfamiliar repositories in minutes
        </h1>
        <p className="text-lg text-slate-400 font-medium">
          Paste any public GitHub repository URL. Our pipeline clones, indexes, and sets up a local RAG model for code search and chat.
        </p>
      </div>

      {/* Import Form Container */}
      <div className="w-full max-w-2xl mb-16">
        {!activeImportRepo ? (
          <form onSubmit={handleImport} className="relative flex items-center p-1.5 bg-slate-900/60 border border-white/10 rounded-2xl focus-within:border-indigo-500/50 shadow-2xl focus-within:shadow-indigo-500/10 transition-all duration-300 backdrop-blur-md">
            <div className="pl-3.5 text-slate-400">
              <GitHubIcon className="w-5 h-5 shrink-0" />
            </div>
            <input 
              type="text" 
              placeholder="Paste public GitHub repository URL (e.g., https://github.com/fastapi/fastapi)..." 
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={isLoading}
              className="w-full px-3 py-3 bg-transparent text-white placeholder-slate-500 text-sm focus:outline-none"
            />
            <button 
              type="submit" 
              disabled={isLoading || !githubUrl.trim()}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:opacity-50 text-white font-medium text-sm rounded-xl transition-all shadow-lg hover:shadow-indigo-600/20 active:scale-95 shrink-0"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              <span>Analyze</span>
            </button>
          </form>
        ) : (
          /* Active Import Process View */
          <div className="p-6 bg-slate-900/80 border border-indigo-500/30 rounded-2xl shadow-2xl glow-active backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                <span className="font-semibold text-white">Analyzing {activeImportRepo.owner}/{activeImportRepo.name}</span>
              </div>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 font-mono border border-indigo-500/20 capitalize">
                Status: {activeImportRepo.status}
              </span>
            </div>

            {/* Custom Log Terminal UI */}
            <div className="bg-slate-950 p-4 rounded-xl border border-white/5 font-mono text-xs text-slate-300 min-h-[140px] flex flex-col justify-end gap-1.5 overflow-hidden">
              {importLogs.map((log, idx) => (
                <div key={idx} className={`flex items-start gap-2 ${idx === importLogs.length - 1 ? 'text-indigo-400 font-semibold' : 'text-slate-400'}`}>
                  <span className="text-indigo-500 select-none">&gt;</span>
                  <span>{log}</span>
                </div>
              ))}
            </div>

            {activeImportRepo.status === "failed" && (
              <div className="mt-4 flex items-start gap-2 p-3 bg-red-950/20 border border-red-500/30 rounded-lg text-xs text-red-300">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Analysis failed: </span>
                  <span>{activeImportRepo.error_message || "Unknown internal error"}</span>
                  <button 
                    onClick={() => { setActiveImportRepo(null); setIsLoading(false); }}
                    className="block mt-2 underline font-medium text-red-400 cursor-pointer"
                  >
                    Reset & try again
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2.5 p-3.5 bg-red-950/20 border border-red-500/20 rounded-xl text-sm text-red-300">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Previously Imported Repositories Grid */}
      <div className="w-full max-w-5xl">
        <div className="flex items-center justify-between mb-6 pb-2 border-b border-white/5">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <span>Analyzed Repositories</span>
          </h2>
          <span className="text-xs text-slate-500 font-semibold">{repositories.length} Total</span>
        </div>

        {repositories.length === 0 ? (
          <div className="text-center py-16 bg-slate-900/20 border border-white/5 rounded-2xl backdrop-blur-sm">
            <FileCode className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 font-medium">No repositories analyzed yet.</p>
            <p className="text-slate-500 text-xs mt-1">Paste a GitHub link above to kickstart ingestion.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {repositories.map((repo) => (
              <div 
                key={repo.id}
                onClick={() => {
                  if (repo.status === "ready") {
                    router.push(`/dashboard/${repo.id}`);
                  } else {
                    setActiveImportRepo(repo);
                  }
                }}
                className={`glass-card p-5 rounded-2xl flex flex-col justify-between h-48 cursor-pointer relative group overflow-hidden ${
                  repo.status !== "ready" ? "border-amber-500/20 opacity-80" : ""
                }`}
              >
                {/* Tech indicator badge line */}
                <div className="absolute top-0 left-0 w-full h-[3px] bg-indigo-500/10 group-hover:bg-gradient-to-r group-hover:from-indigo-500 group-hover:to-sky-400 transition-all duration-300" />

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-white/5 text-slate-400 font-mono">
                      {repo.primary_language || "Config"}
                    </span>
                    {repo.status !== "ready" && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono animate-pulse capitalize">
                        {repo.status}
                      </span>
                    )}
                  </div>
                  
                  <h3 className="font-bold text-lg text-white group-hover:text-indigo-300 transition-colors line-clamp-1">
                    {repo.name}
                  </h3>
                  <span className="text-xs text-slate-500 font-semibold block mb-2.5">
                    by {repo.owner}
                  </span>
                  
                  <p className="text-slate-400 text-xs line-clamp-2 leading-relaxed font-normal">
                    {repo.description || "No repository description provided."}
                  </p>
                </div>

                <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{new Date(repo.created_at).toLocaleDateString()}</span>
                  </div>
                  
                  <div className="flex items-center gap-1.5">
                    <button 
                      onClick={(e) => handleDeleteRepo(repo.id, e)}
                      className="p-1.5 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-all cursor-pointer"
                      title="Delete Analysis"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <div className="p-1.5 rounded-lg bg-indigo-500/5 text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
