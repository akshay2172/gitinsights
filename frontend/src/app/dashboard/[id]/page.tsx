"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  Folder, 
  File, 
  ChevronDown, 
  ChevronRight, 
  BookOpen, 
  Search, 
  MessageSquare, 
  ArrowLeft, 
  ExternalLink, 
  Code2, 
  Layers, 
  FolderGit2, 
  Compass, 
  Send,
  Sparkles,
  HelpCircle,
  FileText,
  Loader2,
  X,
  Plus
} from "lucide-react";

const API_BASE = "http://localhost:8000/api";

// Types
interface TreeNode {
  name: string;
  type: "file" | "directory";
  path?: string;
  language?: string;
  size?: number;
  children?: TreeNode[];
}

interface RepositoryDetails {
  id: number;
  name: string;
  owner: string;
  github_url: string;
  description: string | null;
  primary_language: string | null;
  status: string;
  summary: string | null;
  tech_stack: string | null;
  folder_overview: string | null;
  important_modules: string | null;
  starting_point: string | null;
  languages: Record<string, number>;
  dependencies: string[];
}

interface FileDetails {
  path: string;
  name: string;
  language: string;
  size: number;
  content: string;
  purpose_explanation: string | null;
  functions: Array<{ name: string; start_line: number; end_line: number; args?: string[]; is_async?: boolean }>;
  classes: Array<{ name: string; start_line: number; end_line: number; bases?: string[] }>;
  imports: string[];
}

interface SearchResult {
  file_path: string;
  language: string;
  snippet: string;
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

// Tree Node Item Component (Recursive)
interface TreeItemProps {
  node: TreeNode;
  level: number;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}

function TreeItem({ node, level, selectedPath, onSelectFile }: TreeItemProps) {
  const [isOpen, setIsOpen] = useState(false);
  const isDirectory = node.type === "directory";
  const isSelected = selectedPath === node.path;

  const toggleOpen = () => {
    if (isDirectory) setIsOpen(!isOpen);
  };

  const handleSelect = () => {
    if (!isDirectory && node.path) {
      onSelectFile(node.path);
    } else {
      toggleOpen();
    }
  };

  return (
    <div>
      <div 
        onClick={handleSelect}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        className={`flex items-center gap-2 py-1.5 pr-2 text-xs font-medium cursor-pointer rounded-md transition-all select-none ${
          isSelected 
            ? "bg-indigo-500/10 text-indigo-300 border-l-2 border-indigo-500" 
            : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
        }`}
      >
        {isDirectory ? (
          <>
            {isOpen ? <ChevronDown className="w-3.5 h-3.5 shrink-0 text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0 text-slate-500" />}
            <Folder className={`w-4 h-4 shrink-0 ${isOpen ? "text-indigo-400" : "text-indigo-400/80"}`} />
          </>
        ) : (
          <>
            <span className="w-3.5" />
            <File className={`w-4 h-4 shrink-0 ${isSelected ? "text-indigo-400" : "text-slate-500"}`} />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </div>
      
      {isDirectory && isOpen && node.children && (
        <div className="mt-0.5">
          {node.children.map((child, idx) => (
            <TreeItem 
              key={idx} 
              node={child} 
              level={level + 1} 
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const params = useParams();
  const router = useRouter();
  const repoIdStr = params?.id as string;
  const repoId = parseInt(repoIdStr);

  const [activeTab, setActiveTab] = useState<"overview" | "search" | "chat">("overview");
  const [repoDetails, setRepoDetails] = useState<RepositoryDetails | null>(null);
  const [treeData, setTreeData] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);

  // File Viewer States
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [fileDetails, setFileDetails] = useState<FileDetails | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileExplain, setFileExplain] = useState<string | null>(null);
  const [fileExplainLoading, setFileExplainLoading] = useState(false);
  
  // Custom Function Explanation state
  const [selectedFunction, setSelectedFunction] = useState<{ name: string; code: string } | null>(null);
  const [functionExplain, setFunctionExplain] = useState<string | null>(null);
  const [functionExplainLoading, setFunctionExplainLoading] = useState(false);

  // Code Search states
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Repository Chat states
  const [chatQuery, setChatQuery] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Fetch Repository core metadata
  const loadRepoData = useCallback(async () => {
    try {
      setLoading(true);
      const resMetadata = await fetch(`${API_BASE}/repos/${repoId}`);
      if (!resMetadata.ok) throw new Error("Repo metadata not found");
      const metadata = await resMetadata.json();
      setRepoDetails(metadata);

      const resTree = await fetch(`${API_BASE}/explorer/${repoId}/tree`);
      if (resTree.ok) {
        const tree = await resTree.json();
        setTreeData(tree);
      }
      setLoading(false);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    if (repoId) {
      loadRepoData();
    }
  }, [repoId, loadRepoData]);

  // Scroll chat bottom helper
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Load code file viewer
  const handleSelectFile = async (path: string) => {
    setSelectedFilePath(path);
    setFileLoading(true);
    setFileDetails(null);
    setFileExplain(null);
    setSelectedFunction(null);
    setFunctionExplain(null);

    try {
      const res = await fetch(`${API_BASE}/explorer/${repoId}/file?path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const data: FileDetails = await res.json();
        setFileDetails(data);
        setFileLoading(false);

        // Instantly trigger AI file explanation caching call
        fetchFileExplanation(path);
      } else {
        setFileLoading(false);
      }
    } catch (err) {
      console.error(err);
      setFileLoading(false);
    }
  };

  // Fetch AI file explanation
  const fetchFileExplanation = async (path: string) => {
    setFileExplainLoading(true);
    try {
      const res = await fetch(`${API_BASE}/explain/${repoId}/file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path }),
      });
      if (res.ok) {
        const data = await res.json();
        setFileExplain(data.explanation);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setFileExplainLoading(false);
    }
  };

  // Explain a selected function
  const handleExplainFunction = async (funcName: string, startLine: number, endLine: number) => {
    if (!fileDetails) return;
    
    // Extract function code block
    const lines = fileDetails.content.split("\n");
    const funcCode = lines.slice(startLine - 1, endLine).join("\n");
    
    setSelectedFunction({ name: funcName, code: funcCode });
    setFunctionExplain(null);
    setFunctionExplainLoading(true);

    try {
      const res = await fetch(`${API_BASE}/explain/${repoId}/function`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: fileDetails.path,
          function_name: funcName,
          function_code: funcCode
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setFunctionExplain(data.explanation);
      }
    } catch (err) {
      console.error(err);
      setFunctionExplain("Failed to generate function explanation.");
    } finally {
      setFunctionExplainLoading(false);
    }
  };

  // Execute Code Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchLoading(true);
    try {
      const res = await fetch(`${API_BASE}/search/${repoId}?q=${encodeURIComponent(searchQuery.trim())}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSearchLoading(false);
    }
  };

  // Execute Chat message submission
  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatQuery.trim() || chatLoading) return;

    const userMsg = chatQuery.trim();
    setChatQuery("");
    setChatHistory(prev => [...prev, { role: "user", content: userMsg }]);
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat/${repoId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userMsg,
          chat_history: chatHistory.map(h => ({ role: h.role, content: h.content }))
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, { 
          role: "assistant", 
          content: data.answer,
          sources: data.sources
        }]);
      } else {
        setChatHistory(prev => [...prev, { 
          role: "assistant", 
          content: "Sorry, I encountered an error communicating with the chat pipeline." 
        }]);
      }
    } catch (err) {
      console.error(err);
      setChatHistory(prev => [...prev, { 
        role: "assistant", 
        content: "Network error. Please check if backend is running." 
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] flex flex-col items-center justify-center text-slate-300">
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
        <span className="text-sm font-semibold tracking-wide font-mono">Loading GitInsight workspace...</span>
      </div>
    );
  }

  if (!repoDetails) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] flex flex-col items-center justify-center text-slate-300">
        <span className="text-red-400 font-bold mb-2">Error</span>
        <span>Repository workspace details could not be found.</span>
        <button 
          onClick={() => router.push("/")}
          className="mt-4 flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Landing</span>
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen bg-[#0a0e1a] flex flex-col overflow-hidden text-slate-200">
      
      {/* Top Navbar */}
      <header className="h-14 border-b border-white/5 flex items-center justify-between px-4 bg-slate-950/80 backdrop-blur-md shrink-0 select-none">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push("/")}
            className="p-1.5 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-all cursor-pointer"
            title="Back to Repositories"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          
          <div className="h-4 w-[1px] bg-white/10" />
          
          <div className="flex items-center gap-2">
            <span className="font-bold text-white text-sm">{repoDetails.name}</span>
            <span className="text-xs text-slate-500">by {repoDetails.owner}</span>
          </div>
          
          {repoDetails.github_url && (
            <a 
              href={repoDetails.github_url} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-slate-500 hover:text-slate-300 transition-colors p-1"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        {/* Global tab selectors for dashboard views */}
        <div className="flex items-center gap-1">
          <button 
            onClick={() => { setSelectedFilePath(null); setActiveTab("overview"); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "overview" && !selectedFilePath
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/10" 
                : "text-slate-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>Overview</span>
          </button>
          <button 
            onClick={() => { setSelectedFilePath(null); setActiveTab("search"); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "search" && !selectedFilePath
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/10" 
                : "text-slate-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            <span>Code Search</span>
          </button>
          <button 
            onClick={() => { setSelectedFilePath(null); setActiveTab("chat"); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === "chat" && !selectedFilePath
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/10" 
                : "text-slate-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Code Chat</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Frame */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Sidebar - File Tree Explorer */}
        <aside className="w-64 border-r border-white/5 bg-slate-950/40 flex flex-col overflow-hidden select-none">
          <div className="p-3 border-b border-white/5 flex items-center justify-between shrink-0">
            <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase font-mono">Workspace Explorer</span>
            <span className="text-[10px] font-semibold bg-white/5 px-2 py-0.5 rounded text-slate-400 font-mono capitalize">
              {repoDetails.primary_language}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2.5 space-y-0.5">
            {treeData.map((node, idx) => (
              <TreeItem 
                key={idx} 
                node={node} 
                level={0} 
                selectedPath={selectedFilePath}
                onSelectFile={handleSelectFile}
              />
            ))}
            {treeData.length === 0 && (
              <div className="text-center py-8 text-slate-600 text-xs">No indexed files.</div>
            )}
          </div>
        </aside>

        {/* Content Viewer Layout */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-900/10">
          {selectedFilePath ? (
            
            /* active file view mode */
            <div className="flex-1 flex overflow-hidden">
              {fileLoading ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
                  <Loader2 className="w-8 h-8 text-indigo-500 animate-spin mb-2" />
                  <span className="text-xs font-mono">Reading source content...</span>
                </div>
              ) : (
                fileDetails && (
                  <>
                    {/* Left Code Editor viewport (60% width) */}
                    <div className="flex-[3] flex flex-col border-r border-white/5 overflow-hidden">
                      <div className="h-10 px-4 bg-slate-950/60 border-b border-white/5 flex items-center justify-between shrink-0 select-none">
                        <div className="flex items-center gap-2">
                          <Code2 className="w-4 h-4 text-indigo-400" />
                          <span className="text-xs font-semibold text-slate-200 font-mono truncate max-w-sm">{fileDetails.path}</span>
                        </div>
                        <button 
                          onClick={() => setSelectedFilePath(null)}
                          className="p-1 hover:bg-white/5 rounded text-slate-400 hover:text-white transition-all cursor-pointer"
                          title="Close file"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Code line viewer container */}
                      <div className="flex-1 overflow-auto bg-slate-950/40 p-4 font-mono text-xs leading-relaxed flex">
                        {/* Line number indicators */}
                        <div className="text-right text-slate-600 select-none pr-4 border-r border-white/5 space-y-1.5 shrink-0">
                          {fileDetails.content.split("\n").map((_, idx) => (
                            <div key={idx} className="h-[18px]">{idx + 1}</div>
                          ))}
                        </div>
                        
                        {/* Source code lines */}
                        <pre className="pl-4 text-slate-300 space-y-1.5 overflow-x-visible w-full select-text">
                          {fileDetails.content.split("\n").map((line, idx) => (
                            <code key={idx} className="block h-[18px] hover:bg-white/5 whitespace-pre">
                              {line || " "}
                            </code>
                          ))}
                        </pre>
                      </div>
                    </div>

                    {/* Right AI Explanation side panel (40% width) */}
                    <div className="flex-[2] flex flex-col overflow-hidden bg-slate-950/20 select-text">
                      <div className="h-10 px-4 bg-slate-950/60 border-b border-white/5 flex items-center shrink-0 select-none">
                        <Sparkles className="w-4 h-4 text-indigo-400 mr-2" />
                        <span className="text-xs font-bold tracking-wider text-slate-300 uppercase font-mono">AI Explanation</span>
                      </div>

                      <div className="flex-1 overflow-y-auto p-4 space-y-6">
                        
                        {/* Custom Function Analyzer details card overlay */}
                        {selectedFunction && (
                          <div className="p-4 bg-indigo-500/5 border border-indigo-500/20 rounded-xl relative">
                            <button 
                              onClick={() => setSelectedFunction(null)}
                              className="absolute top-3 right-3 p-1 rounded-md hover:bg-white/5 text-slate-400 hover:text-white transition-all cursor-pointer"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                            <h4 className="text-xs font-bold text-indigo-300 font-mono mb-2 flex items-center gap-1.5">
                              <Code2 className="w-3.5 h-3.5" />
                              <span>Function: {selectedFunction.name}()</span>
                            </h4>
                            
                            {functionExplainLoading ? (
                              <div className="py-6 flex flex-col items-center justify-center text-slate-500 text-xs">
                                <Loader2 className="w-5 h-5 text-indigo-400 animate-spin mb-2" />
                                <span>Analyzing logic parameters...</span>
                              </div>
                            ) : (
                              <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed prose prose-invert font-normal">
                                {functionExplain}
                              </div>
                            )}
                          </div>
                        )}

                        {/* File Level Technical Explanation */}
                        <div>
                          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5 font-mono select-none">File Summary</h3>
                          {fileExplainLoading ? (
                            <div className="py-8 flex flex-col items-center justify-center text-slate-600 text-xs">
                              <Loader2 className="w-6 h-6 text-indigo-400 animate-spin mb-2" />
                              <span>Parsing module layout...</span>
                            </div>
                          ) : (
                            <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed font-normal prose prose-invert">
                              {fileExplain || "No summary details generated."}
                            </div>
                          )}
                        </div>

                        {/* Extracted functions checklist */}
                        {fileDetails.functions.length > 0 && (
                          <div>
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 font-mono select-none">
                              Functions ({fileDetails.functions.length})
                            </h3>
                            <div className="grid grid-cols-1 gap-2">
                              {fileDetails.functions.map((fn, idx) => (
                                <div 
                                  key={idx}
                                  onClick={() => handleExplainFunction(fn.name, fn.start_line, fn.end_line)}
                                  className="p-2.5 bg-slate-900/50 hover:bg-indigo-500/10 border border-white/5 hover:border-indigo-500/30 rounded-lg cursor-pointer flex items-center justify-between group transition-all"
                                >
                                  <div>
                                    <span className="font-mono text-xs text-indigo-400 group-hover:text-indigo-300 font-semibold">
                                      {fn.name}()
                                    </span>
                                    {fn.is_async && (
                                      <span className="ml-2 text-[9px] bg-slate-800 text-slate-400 px-1 py-0.5 rounded font-mono">async</span>
                                    )}
                                  </div>
                                  <span className="text-[10px] text-slate-500 font-mono group-hover:text-indigo-400 transition-colors">
                                    Lines {fn.start_line}-{fn.end_line}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Extracted classes checklist */}
                        {fileDetails.classes.length > 0 && (
                          <div>
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 font-mono select-none">
                              Classes ({fileDetails.classes.length})
                            </h3>
                            <div className="grid grid-cols-1 gap-2">
                              {fileDetails.classes.map((cl, idx) => (
                                <div 
                                  key={idx}
                                  className="p-2.5 bg-slate-900/50 border border-white/5 rounded-lg flex items-center justify-between"
                                >
                                  <span className="font-mono text-xs text-sky-400 font-semibold">{cl.name}</span>
                                  <span className="text-[10px] text-slate-500 font-mono">Lines {cl.start_line}-{cl.end_line}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Extracted Imports checklist */}
                        {fileDetails.imports.length > 0 && (
                          <div>
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 font-mono select-none">Imports</h3>
                            <div className="flex flex-wrap gap-1.5">
                              {fileDetails.imports.map((imp, idx) => (
                                <span key={idx} className="px-2 py-1 bg-white/5 border border-white/5 rounded text-[10px] font-mono text-slate-400">
                                  {imp}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )
              )}
            </div>
          ) : (
            /* default dashboard tab selector modes */
            <div className="flex-1 overflow-y-auto p-6 md:p-8">
              
              {activeTab === "overview" && (
                <div className="max-w-4xl space-y-6">
                  
                  {/* Repo summary card */}
                  <div className="p-6 bg-slate-950/40 border border-white/5 rounded-2xl">
                    <div className="flex items-center gap-2 mb-4 text-indigo-400">
                      <BookOpen className="w-5 h-5" />
                      <h2 className="text-lg font-bold text-white">Repository Summary</h2>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed font-normal whitespace-pre-line">
                      {repoDetails.summary || "Summary generation pending."}
                    </p>
                  </div>

                  {/* Languages Stats list */}
                  {Object.keys(repoDetails.languages).length > 0 && (
                    <div className="p-6 bg-slate-950/40 border border-white/5 rounded-2xl">
                      <h3 className="text-sm font-bold text-white mb-3">Languages Distribution</h3>
                      <div className="flex w-full h-2.5 bg-slate-800 rounded-full overflow-hidden mb-4">
                        {Object.entries(repoDetails.languages).map(([lang, pct], idx) => {
                          const hues = [240, 200, 280, 160, 320];
                          const color = `hsl(${hues[idx % hues.length]}, 70%, 55%)`;
                          return (
                            <div 
                              key={lang}
                              style={{ width: `${pct}%`, backgroundColor: color }}
                              title={`${lang}: ${pct}%`}
                            />
                          );
                        })}
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-2">
                        {Object.entries(repoDetails.languages).map(([lang, pct], idx) => {
                          const hues = [240, 200, 280, 160, 320];
                          const color = `hsl(${hues[idx % hues.length]}, 70%, 65%)`;
                          return (
                            <div key={lang} className="flex items-center gap-1.5 text-xs text-slate-400">
                              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                              <span className="font-semibold text-slate-300">{lang}</span>
                              <span className="text-slate-500 font-mono">({pct}%)</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Grid layout for tech stack & suggested onboarding */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    {/* Tech Stack card */}
                    <div className="p-5 bg-slate-950/40 border border-white/5 rounded-2xl">
                      <div className="flex items-center gap-2 mb-3.5 text-sky-400">
                        <Layers className="w-5 h-5" />
                        <h3 className="font-bold text-white text-sm">Tech Stack & Packages</h3>
                      </div>
                      <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed prose prose-invert">
                        {repoDetails.tech_stack || "Extracted dependencies are listing below."}
                      </div>
                      
                      {repoDetails.dependencies.length > 0 && (
                        <div className="mt-4">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2 font-mono">Extracted Packages</span>
                          <div className="flex flex-wrap gap-1.5">
                            {repoDetails.dependencies.slice(0, 24).map((dep, idx) => (
                              <span key={idx} className="px-2 py-0.5 bg-sky-500/10 text-sky-300 border border-sky-500/25 rounded text-[10px] font-mono">
                                {dep}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Onboarding Guide card */}
                    <div className="p-5 bg-slate-950/40 border border-white/5 rounded-2xl">
                      <div className="flex items-center gap-2 mb-3.5 text-violet-400">
                        <Compass className="w-5 h-5" />
                        <h3 className="font-bold text-white text-sm">Starting Point Guide</h3>
                      </div>
                      <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed prose prose-invert font-normal">
                        {repoDetails.starting_point || "Onboarding suggestions not yet defined."}
                      </div>
                    </div>

                    {/* Folder Structure Overview card */}
                    <div className="p-5 bg-slate-950/40 border border-white/5 rounded-2xl md:col-span-2">
                      <div className="flex items-center gap-2 mb-3.5 text-emerald-400">
                        <FolderGit2 className="w-5 h-5" />
                        <h3 className="font-bold text-white text-sm">Directory Architecture</h3>
                      </div>
                      <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed prose prose-invert font-normal">
                        {repoDetails.folder_overview || "Folder layout details pending."}
                      </div>
                    </div>

                    {/* Important Modules card */}
                    <div className="p-5 bg-slate-950/40 border border-white/5 rounded-2xl md:col-span-2">
                      <div className="flex items-center gap-2 mb-3.5 text-amber-400">
                        <FileText className="w-5 h-5" />
                        <h3 className="font-bold text-white text-sm">Important Modules & Files</h3>
                      </div>
                      <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed prose prose-invert font-normal">
                        {repoDetails.important_modules || "Key configurations not yet identified."}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "search" && (
                <div className="max-w-4xl space-y-6">
                  {/* Search Query Bar */}
                  <div className="p-6 bg-slate-950/40 border border-white/5 rounded-2xl">
                    <h2 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                      <Search className="w-5 h-5 text-indigo-400" />
                      <span>Semantic Code Search</span>
                    </h2>
                    <p className="text-xs text-slate-400 mb-4 font-normal">
                      Query the codebase conceptually (e.g. "where is the token created" or "email validation rules").
                    </p>

                    <form onSubmit={handleSearch} className="flex gap-2.5">
                      <input 
                        type="text" 
                        placeholder="Search for functions, variables, behaviors or logic implementations..." 
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-slate-950 border border-white/10 focus:border-indigo-500/50 rounded-xl px-4 py-2.5 text-sm focus:outline-none text-white placeholder-slate-500"
                      />
                      <button 
                        type="submit"
                        disabled={searchLoading || !searchQuery.trim()}
                        className="flex items-center gap-1.5 px-6 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-all cursor-pointer select-none"
                      >
                        {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Search</span>}
                      </button>
                    </form>
                  </div>

                  {/* Similarity Results Grid */}
                  <div className="space-y-4">
                    {searchResults.map((res, idx) => (
                      <div 
                        key={idx}
                        onClick={() => handleSelectFile(res.file_path)}
                        className="p-4 bg-slate-950/40 hover:bg-indigo-500/5 border border-white/5 hover:border-indigo-500/25 rounded-2xl cursor-pointer group transition-all duration-300"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 font-mono">
                            {res.file_path}
                          </span>
                          <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                            {res.language}
                          </span>
                        </div>
                        
                        <div className="p-3 bg-slate-955 rounded-xl border border-white/5 overflow-x-auto code-font text-xs text-slate-300 max-h-48 overflow-y-hidden">
                          <pre>{res.snippet}</pre>
                        </div>
                      </div>
                    ))}
                    
                    {!searchLoading && searchResults.length === 0 && searchQuery && (
                      <div className="text-center py-12 text-slate-500 text-sm">
                        No matches found. Try refining your wording.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === "chat" && (
                <div className="max-w-4xl h-[calc(100vh-12rem)] flex flex-col bg-slate-950/40 border border-white/5 rounded-2xl overflow-hidden">
                  
                  {/* Chat feed headers */}
                  <div className="p-4 border-b border-white/5 bg-slate-950/30 flex items-center justify-between shrink-0 select-none">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4.5 h-4.5 text-indigo-400" />
                      <span className="text-sm font-bold text-white">Repository Assistant</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono font-medium">Model: gemini-1.5-flash</span>
                  </div>

                  {/* Chat message threads */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text">
                    
                    {/* Welcome Bubble */}
                    <div className="flex items-start gap-3 max-w-[85%]">
                      <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl shrink-0">
                        <Sparkles className="w-4 h-4" />
                      </div>
                      <div className="p-3.5 bg-slate-900/80 border border-white/5 rounded-2xl text-xs text-slate-300 leading-relaxed font-normal">
                        Hello! I am GitInsight. I have indexed this repository's codebase. Ask me anything about the folders, architecture, auth flows, module behaviors, or code implementations.
                      </div>
                    </div>

                    {chatHistory.map((msg, idx) => (
                      <div 
                        key={idx}
                        className={`flex items-start gap-3 max-w-[85%] ${
                          msg.role === "user" ? "ml-auto flex-row-reverse" : ""
                        }`}
                      >
                        <div className={`p-2 rounded-xl shrink-0 ${
                          msg.role === "user" 
                            ? "bg-slate-800 border border-white/5 text-slate-300" 
                            : "bg-indigo-500/10 border border-indigo-500/20 text-indigo-400"
                        }`}>
                          {msg.role === "user" ? <HelpCircle className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                        </div>
                        
                        <div className="flex flex-col gap-2">
                          <div className={`p-3.5 rounded-2xl text-xs leading-relaxed font-normal prose prose-invert ${
                            msg.role === "user"
                              ? "bg-indigo-600 text-white font-medium shadow-md shadow-indigo-600/10"
                              : "bg-slate-900/80 border border-white/5 text-slate-300 whitespace-pre-wrap"
                          }`}>
                            {msg.content}
                          </div>
                          
                          {/* Citation Source Tags */}
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 pl-2.5">
                              <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider font-mono mr-1 self-center">Sources:</span>
                              {msg.sources.map((src, sIdx) => (
                                <button
                                  key={sIdx}
                                  onClick={() => handleSelectFile(src)}
                                  className="flex items-center gap-1 px-2 py-0.5 bg-white/5 hover:bg-indigo-500/10 border border-white/5 hover:border-indigo-500/35 rounded text-[10px] font-mono text-slate-400 hover:text-indigo-300 cursor-pointer transition-colors"
                                >
                                  <FileText className="w-3 h-3" />
                                  <span>{src}</span>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {chatLoading && (
                      <div className="flex items-start gap-3 max-w-[85%]">
                        <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl shrink-0">
                          <Loader2 className="w-4 h-4 animate-spin" />
                        </div>
                        <div className="p-3 bg-slate-900/40 border border-white/5 rounded-2xl text-xs text-slate-500 italic">
                          Searching index and composing response...
                        </div>
                      </div>
                    )}
                    
                    <div ref={chatBottomRef} />
                  </div>

                  {/* Chat input box */}
                  <form onSubmit={handleSendChat} className="p-4 border-t border-white/5 bg-slate-950/20 flex gap-2 shrink-0">
                    <input 
                      type="text" 
                      placeholder="Ask a question about the code (e.g., 'How are routers structured?', 'Explain authentication')..." 
                      value={chatQuery}
                      onChange={(e) => setChatQuery(e.target.value)}
                      disabled={chatLoading}
                      className="w-full bg-slate-950 border border-white/10 focus:border-indigo-500/50 rounded-xl px-4 py-2.5 text-sm focus:outline-none text-white placeholder-slate-500"
                    />
                    <button 
                      type="submit"
                      disabled={chatLoading || !chatQuery.trim()}
                      className="p-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:opacity-50 text-white rounded-xl transition-all cursor-pointer flex items-center justify-center shrink-0"
                    >
                      <Send className="w-4.5 h-4.5" />
                    </button>
                  </form>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
