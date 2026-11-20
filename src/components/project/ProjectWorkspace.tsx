import React, { useState, useRef } from 'react';
import {
  BookOpen,
  MessageSquare,
  FileText,
  Bookmark,
  Compass,
  History,
  Plus,
  Trash2,
  FileUp,
  X,
  Edit3,
  Check,
  Sparkles,
  ArrowLeft,
  Layers,
  Search,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { MessageItem } from '../message/MessageItem';
import { ChatInput } from '../input/ChatInput';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { ProjectNote } from '../../types';
import { formatRelativeTime } from '../../utils/date';
import { cn } from '../../utils/cn';

type ProjectTab = 'chat' | 'papers' | 'notes' | 'instructions' | 'activity';

export const ProjectWorkspace: React.FC = () => {
  const {
    activeProjectId,
    activeProject,
    projectNotes,
    projectActivity,
    projectDocuments,
    messages,
    isGenerating,
    sendMessage,
    stopGeneration,
    regenerateLastResponse,
    uploadProjectDocument,
    removeDocument,
    saveProjectNote,
    deleteProjectNote,
    updateProject,
    deleteProject,
    setWorkspaceMode,
    settings,
  } = useApp();

  const [activeTab, setActiveTab] = useState<ProjectTab>('chat');
  const [isDeletingProject, setIsDeletingProject] = useState(false);
  const [isEditingHeader, setIsEditingHeader] = useState(false);
  const [editedTitle, setEditedTitle] = useState(activeProject?.name || '');
  const [editedDescription, setEditedDescription] = useState(activeProject?.description || '');

  // Instructions state
  const [instructionsText, setInstructionsText] = useState(
    activeProject?.custom_instructions || activeProject?.instructions || ''
  );
  const [isSavingInstructions, setIsSavingInstructions] = useState(false);
  const [instructionsSavedMessage, setInstructionsSavedMessage] = useState(false);

  // New Note Modal
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteCategory, setNoteCategory] = useState<'finding' | 'methodology' | 'experiment' | 'note'>('finding');
  const [noteContent, setNoteContent] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteSearch, setNoteSearch] = useState('');
  const [selectedNoteCategoryFilter, setSelectedNoteCategoryFilter] = useState<string>('all');

  // File upload input ref
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  if (!activeProject) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-moso-950 text-moso-400">
        <BookOpen className="h-12 w-12 text-moso-600 mb-3" />
        <h3 className="text-lg font-semibold text-moso-200">No Research Project Selected</h3>
        <p className="text-sm text-moso-400 mt-1 max-w-sm text-center">
          Choose a research project from the sidebar or create a new one to begin your academic analysis.
        </p>
        <Button
          variant="primary"
          onClick={() => setWorkspaceMode('chat')}
          className="mt-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to General Chat
        </Button>
      </div>
    );
  }

  const handleSaveHeader = async () => {
    if (activeProjectId && editedTitle.trim()) {
      await updateProject(activeProjectId, {
        name: editedTitle.trim(),
        description: editedDescription.trim(),
      });
      setIsEditingHeader(false);
    }
  };

  const handleSaveInstructions = async () => {
    if (!activeProjectId) return;
    setIsSavingInstructions(true);
    await updateProject(activeProjectId, {
      instructions: instructionsText,
    });
    setIsSavingInstructions(false);
    setInstructionsSavedMessage(true);
    setTimeout(() => setInstructionsSavedMessage(false), 2500);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      await uploadProjectDocument(file);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload paper');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleOpenNewNoteModal = (note?: ProjectNote) => {
    if (note) {
      setEditingNoteId(note.id);
      setNoteTitle(note.title);
      setNoteCategory(note.category as any);
      setNoteContent(note.content);
    } else {
      setEditingNoteId(null);
      setNoteTitle('');
      setNoteCategory('finding');
      setNoteContent('');
    }
    setIsNoteModalOpen(true);
  };

  const handleSaveNote = async () => {
    if (!activeProjectId || !noteTitle.trim() || !noteContent.trim()) return;
    await saveProjectNote(noteTitle.trim(), noteContent.trim(), noteCategory);
    setIsNoteModalOpen(false);
  };

  const filteredNotes = projectNotes.filter((note) => {
    const matchesCategory = selectedNoteCategoryFilter === 'all' || note.category === selectedNoteCategoryFilter;
    const matchesSearch =
      !noteSearch.trim() ||
      note.title.toLowerCase().includes(noteSearch.toLowerCase()) ||
      note.content.toLowerCase().includes(noteSearch.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-moso-950 relative">
      {/* Workspace Header Banner */}
      <div className="border-b border-moso-800/80 bg-moso-900/80 backdrop-blur-md px-3 sm:px-5 py-3 sm:py-3.5 z-10 shrink-0">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-2.5 sm:gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setWorkspaceMode('chat')}
              className="p-1.5 rounded-lg bg-moso-850 hover:bg-moso-800 text-moso-400 hover:text-white transition-colors cursor-pointer shrink-0"
              title="Return to general chat"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div className="p-2 rounded-lg bg-accent-500/10 border border-accent-500/20 text-accent-400 shrink-0">
              <BookOpen className="h-5 w-5" />
            </div>

            {isEditingHeader ? (
              <div className="flex flex-col gap-1.5 flex-1 min-w-0">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="bg-moso-850 border border-moso-700 rounded px-2 py-0.5 text-sm font-semibold text-white focus:outline-none focus:border-accent-500"
                  placeholder="Project Title"
                  autoFocus
                />
                <input
                  type="text"
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  className="bg-moso-850 border border-moso-700 rounded px-2 py-0.5 text-xs text-moso-300 focus:outline-none focus:border-accent-500"
                  placeholder="Short description or research thesis"
                />
                <div className="flex items-center gap-2 mt-1">
                  <Button size="sm" variant="primary" onClick={handleSaveHeader}>
                    <Check className="h-3 w-3 mr-1" /> Save
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setIsEditingHeader(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-semibold text-white truncate">
                    {activeProject.name}
                  </h1>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-accent-500/15 text-accent-400 border border-accent-500/30 font-medium">
                    Research Workspace
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setEditedTitle(activeProject.name);
                      setEditedDescription(activeProject.description || '');
                      setIsEditingHeader(true);
                    }}
                    className="p-1 text-moso-400 hover:text-white rounded hover:bg-moso-800 transition-colors cursor-pointer"
                    title="Edit project details"
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                  </button>
                </div>
                {activeProject.description ? (
                  <p className="text-xs text-moso-400 truncate max-w-xl">
                    {activeProject.description}
                  </p>
                ) : (
                  <p className="text-xs text-moso-500 italic">No description provided</p>
                )}
              </div>
            )}
          </div>

          {/* Quick Actions & Navigation Tabs */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-moso-850 hover:bg-moso-800 border border-moso-750 text-xs text-moso-200 hover:text-white transition-colors cursor-pointer font-medium"
            >
              <FileUp className="h-3.5 w-3.5 text-accent-400" />
              <span>Add Paper</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileUpload}
              className="hidden"
            />

            <button
              type="button"
              onClick={() => handleOpenNewNoteModal()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-600 hover:bg-accent-500 text-xs text-white font-medium transition-colors cursor-pointer shadow-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Note</span>
            </button>

            <button
              type="button"
              onClick={() => setIsDeletingProject(true)}
              className="p-2 rounded-lg bg-moso-850 hover:bg-rose-950/40 text-moso-400 hover:text-rose-400 border border-moso-750 hover:border-rose-900/50 transition-colors cursor-pointer"
              title="Delete research project"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Tab Navigation Row */}
        <div className="max-w-6xl mx-auto flex items-center gap-1 mt-2.5 sm:mt-3.5 border-t border-moso-800/60 pt-2 overflow-x-auto scrollbar-none shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab('chat')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap',
              activeTab === 'chat'
                ? 'bg-moso-800 text-white shadow-xs border border-moso-700/80'
                : 'text-moso-400 hover:text-moso-200 hover:bg-moso-850'
            )}
          >
            <MessageSquare className="h-3.5 w-3.5 text-accent-400" />
            <span>Research Chat</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('papers')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap',
              activeTab === 'papers'
                ? 'bg-moso-800 text-white shadow-xs border border-moso-700/80'
                : 'text-moso-400 hover:text-moso-200 hover:bg-moso-850'
            )}
          >
            <FileText className="h-3.5 w-3.5 text-rose-400" />
            <span>Papers ({projectDocuments.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('notes')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap',
              activeTab === 'notes'
                ? 'bg-moso-800 text-white shadow-xs border border-moso-700/80'
                : 'text-moso-400 hover:text-moso-200 hover:bg-moso-850'
            )}
          >
            <Bookmark className="h-3.5 w-3.5 text-amber-400" />
            <span>Notes ({projectNotes.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('instructions')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap',
              activeTab === 'instructions'
                ? 'bg-moso-800 text-white shadow-xs border border-moso-700/80'
                : 'text-moso-400 hover:text-moso-200 hover:bg-moso-850'
            )}
          >
            <Compass className="h-3.5 w-3.5 text-cyan-400" />
            <span>Instructions</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('activity')}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap',
              activeTab === 'activity'
                ? 'bg-moso-800 text-white shadow-xs border border-moso-700/80'
                : 'text-moso-400 hover:text-moso-200 hover:bg-moso-850'
            )}
          >
            <History className="h-3.5 w-3.5 text-purple-400" />
            <span>Activity</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* TAB 1: RESEARCH CHAT */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            {/* Project Documents Context Indicator */}
            {projectDocuments.length > 0 && (
              <div className="border-b border-moso-800/60 bg-moso-900/50 px-4 py-2 shrink-0">
                <div className="max-w-[880px] lg:max-w-[920px] mx-auto flex items-center justify-between text-xs gap-3">
                  <div className="flex items-center gap-2 text-moso-300 font-medium shrink-0">
                    <BookOpen className="h-3.5 w-3.5 text-accent-400" />
                    <span>Project Library Context ({projectDocuments.length}):</span>
                  </div>
                  <div className="flex items-center gap-2 overflow-x-auto py-0.5 scrollbar-thin">
                    {projectDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-moso-850 border border-moso-750 text-[11px] text-moso-300 shrink-0"
                      >
                        <span className="font-semibold text-rose-400 text-[9px] px-1 py-0.1 rounded bg-rose-500/10 border border-rose-500/20">
                          PDF
                        </span>
                        <span className="font-medium text-white truncate max-w-[150px]" title={doc.filename}>
                          {doc.filename}
                        </span>
                        <span className="text-moso-500 text-[10px]">
                          ({doc.page_count}p)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 md:px-8 space-y-4">
              {messages.length === 0 ? (
                <div className="max-w-2xl mx-auto my-auto text-center py-12 px-4">
                  <div className="h-12 w-12 rounded-xl bg-accent-500/10 border border-accent-500/20 text-accent-400 flex items-center justify-center mx-auto mb-3 shadow-inner">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <h2 className="text-lg font-semibold text-white">
                    {activeProject.name} Research Assistant
                  </h2>
                  <p className="text-xs text-moso-300 mt-2 leading-relaxed max-w-lg mx-auto">
                    Operating at an undergraduate engineering level with formal mathematical rigor, methodology comparisons, and strict FTS5 grounded citations.
                  </p>
                  <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 text-left max-w-lg mx-auto">
                    <button
                      type="button"
                      onClick={() => sendMessage('Summarize the primary research objectives, methodology, and empirical findings across the uploaded papers.')}
                      className="p-3 rounded-lg bg-moso-850 hover:bg-moso-800 border border-moso-750 text-xs text-moso-200 transition-colors text-left"
                    >
                      <p className="font-medium text-white mb-1">Synthesise Research</p>
                      <p className="text-[11px] text-moso-400">Compare methodology and findings across ingested documents</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => sendMessage('Explain the core mathematical equations, loss functions, and variable definitions with formal LaTeX derivations.')}
                      className="p-3 rounded-lg bg-moso-850 hover:bg-moso-800 border border-moso-750 text-xs text-moso-200 transition-colors text-left"
                    >
                      <p className="font-medium text-white mb-1">Mathematical Derivations</p>
                      <p className="text-[11px] text-moso-400">Formal LaTeX explanation of equations and metrics</p>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="max-w-[880px] lg:max-w-[920px] mx-auto space-y-4">
                  {messages.map((message, index) => {
                    const isLatest = index === messages.length - 1;
                    return (
                      <MessageItem
                        key={message.id}
                        message={message}
                        isLatest={isLatest}
                        onRegenerate={regenerateLastResponse}
                        showTimestamp={settings.appearance.showTimestamps}
                      />
                    );
                  })}
                </div>
              )}
            </div>

            {/* Chat Input */}
            <ChatInput
              onSendMessage={sendMessage}
              isGenerating={isGenerating}
              onStopGeneration={stopGeneration}
            />
          </div>
        )}

        {/* TAB 2: PAPERS & DOCUMENTS */}
        {activeTab === 'papers' && (
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 md:p-8">
            <div className="max-w-5xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">Project Ingested Papers</h2>
                  <p className="text-xs text-moso-400 mt-0.5">
                    Research documents are chunked with ~240-word overlapping windows and indexed into SQLite FTS5 for sub-millisecond BM25 keyword retrieval.
                  </p>
                </div>
                <Button
                  variant="primary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  <FileUp className="h-4 w-4 mr-1.5" />
                  {isUploading ? 'Extracting & Indexing...' : 'Upload PDF Paper'}
                </Button>
              </div>

              {uploadError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
                  <span>{uploadError}</span>
                  <button type="button" onClick={() => setUploadError(null)} className="p-1">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              {/* Ingested Papers List */}
              {projectDocuments.length === 0 ? (
                <div className="p-12 text-center rounded-2xl border-2 border-dashed border-moso-800 bg-moso-900/40">
                  <FileText className="h-10 w-10 mx-auto text-moso-600 mb-3" />
                  <h3 className="text-sm font-semibold text-moso-200">No papers uploaded to this project yet</h3>
                  <p className="text-xs text-moso-400 mt-1 max-w-sm mx-auto">
                    Upload academic PDFs (up to 20 MB). Text and equations will be extracted and indexed locally for grounded Q&A.
                  </p>
                  <Button
                    variant="secondary"
                    className="mt-4"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Select PDF Paper
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {projectDocuments.map((doc) => (
                    <div
                      key={doc.id}
                      className="p-4 rounded-xl bg-moso-850/80 border border-moso-750/80 hover:border-moso-650 transition-colors flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-rose-400 text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/20">
                              PDF
                            </span>
                            <h4 className="text-sm font-medium text-white truncate max-w-[240px]" title={doc.filename}>
                              {doc.filename}
                            </h4>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeDocument(doc.id)}
                            className="p-1 text-moso-400 hover:text-rose-400 rounded transition-colors cursor-pointer"
                            title="Remove document from project"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        <div className="flex items-center gap-3 text-[11px] text-moso-400 mt-3 pt-3 border-t border-moso-800">
                          <span className="flex items-center gap-1 font-mono">
                            <Layers className="h-3 w-3 text-moso-500" />
                            {doc.page_count} pages
                          </span>
                          <span className="text-moso-600">•</span>
                          <span className="text-accent-400 font-mono">FTS5 Indexed</span>
                          <span className="text-moso-600">•</span>
                          <span>{formatRelativeTime(doc.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: NOTES & FINDINGS */}
        {activeTab === 'notes' && (
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 md:p-8">
            <div className="max-w-5xl mx-auto space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">Research Notes & Findings</h2>
                  <p className="text-xs text-moso-400 mt-0.5">
                    Save key takeaways, experimental observations, and mathematical formulations for this project.
                  </p>
                </div>
                <Button variant="primary" onClick={() => handleOpenNewNoteModal()}>
                  <Plus className="h-4 w-4 mr-1.5" />
                  New Note
                </Button>
              </div>

              {/* Filter and Search Bar */}
              <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                <div className="w-full sm:w-64">
                  <Input
                    icon={<Search className="h-3.5 w-3.5" />}
                    placeholder="Search notes..."
                    value={noteSearch}
                    onChange={(e) => setNoteSearch(e.target.value)}
                    className="text-xs py-1.5"
                  />
                </div>
                <div className="flex items-center gap-1.5 overflow-x-auto w-full pb-1 sm:pb-0">
                  {['all', 'finding', 'methodology', 'experiment', 'note'].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedNoteCategoryFilter(cat)}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors cursor-pointer',
                        selectedNoteCategoryFilter === cat
                          ? 'bg-accent-500/20 text-accent-300 border border-accent-500/30'
                          : 'bg-moso-850 text-moso-400 hover:text-white border border-moso-750'
                      )}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* Notes Grid */}
              {filteredNotes.length === 0 ? (
                <div className="p-12 text-center rounded-2xl border-2 border-dashed border-moso-800 bg-moso-900/40">
                  <Bookmark className="h-10 w-10 mx-auto text-moso-600 mb-3" />
                  <h3 className="text-sm font-semibold text-moso-200">No notes found</h3>
                  <p className="text-xs text-moso-400 mt-1 max-w-sm mx-auto">
                    Record your hypotheses, model evaluation metrics, or literature synthesis notes.
                  </p>
                  <Button variant="secondary" className="mt-4" onClick={() => handleOpenNewNoteModal()}>
                    Create First Note
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredNotes.map((note) => (
                    <div
                      key={note.id}
                      className="p-4 rounded-xl bg-moso-850 border border-moso-750 hover:border-moso-650 transition-all flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                'text-[10px] font-mono uppercase px-1.5 py-0.5 rounded font-semibold',
                                note.category === 'finding' && 'bg-accent-500/15 text-accent-400 border border-accent-500/30',
                                note.category === 'methodology' && 'bg-purple-500/15 text-purple-400 border border-purple-500/30',
                                note.category === 'experiment' && 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30',
                                note.category === 'note' && 'bg-moso-700/50 text-moso-300 border border-moso-600/50'
                              )}
                            >
                              {note.category}
                            </span>
                            <h4 className="text-sm font-semibold text-white truncate max-w-[200px]">
                              {note.title}
                            </h4>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => handleOpenNewNoteModal(note)}
                              className="p-1 text-moso-400 hover:text-white rounded hover:bg-moso-750 transition-colors cursor-pointer"
                              title="Edit note"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => deleteProjectNote(note.id)}
                              className="p-1 text-moso-400 hover:text-rose-400 rounded hover:bg-moso-750 transition-colors cursor-pointer"
                              title="Delete note"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>

                        <p className="text-xs text-moso-300 leading-relaxed whitespace-pre-wrap line-clamp-4 mt-2">
                          {note.content}
                        </p>
                      </div>

                      <div className="text-[10px] text-moso-500 font-mono mt-4 pt-2 border-t border-moso-800 flex items-center justify-between">
                        <span>Updated {formatRelativeTime(note.updated_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: DOMAIN INSTRUCTIONS */}
        {activeTab === 'instructions' && (
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 md:p-8">
            <div className="max-w-[880px] lg:max-w-[920px] mx-auto space-y-4">
              <div>
                <h2 className="text-base font-semibold text-white">Project Domain Instructions</h2>
                <p className="text-xs text-moso-400 mt-1 leading-relaxed">
                  Provide custom instructions, academic domains, evaluation metric priorities (e.g. ROC-AUC, F1-score), or theoretical frameworks. These instructions are automatically injected into the local inference pipeline for this project.
                </p>
              </div>

              <div className="space-y-3">
                <textarea
                  value={instructionsText}
                  onChange={(e) => setInstructionsText(e.target.value)}
                  rows={10}
                  className="w-full bg-moso-850 border border-moso-750 rounded-xl p-3.5 text-xs text-moso-100 placeholder:text-moso-500 focus:outline-none focus:border-accent-500 font-sans leading-relaxed"
                  placeholder="e.g. Focus on deep learning for biomedical image segmentation. When evaluating algorithms, prioritize Dice score and Hausdorff distance. Compare U-Net with Swin-UNETR transformers and explain any differential equations with KaTeX."
                />

                <div className="flex items-center justify-between">
                  {instructionsSavedMessage ? (
                    <span className="text-xs text-accent-400 font-medium flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5" /> Saved to SQLite workspace configuration
                    </span>
                  ) : (
                    <span className="text-[11px] text-moso-500 font-mono">
                      Scoped strictly to {activeProject.name}
                    </span>
                  )}

                  <Button
                    variant="primary"
                    onClick={handleSaveInstructions}
                    disabled={isSavingInstructions}
                  >
                    {isSavingInstructions ? 'Saving...' : 'Save Instructions'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: ACTIVITY HISTORY */}
        {activeTab === 'activity' && (
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 md:p-8">
            <div className="max-w-[880px] lg:max-w-[920px] mx-auto space-y-4">
              <div>
                <h2 className="text-base font-semibold text-white">Activity Timeline & Audit Log</h2>
                <p className="text-xs text-moso-400 mt-0.5">
                  Chronological trail of research activities, paper uploads, and findings.
                </p>
              </div>

              {projectActivity.length === 0 ? (
                <div className="p-8 text-center text-xs text-moso-500">
                  No activity recorded yet for this workspace.
                </div>
              ) : (
                <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-moso-800">
                  {projectActivity.map((act) => (
                    <div key={act.id} className="relative flex items-start gap-3 text-xs">
                      <div className="absolute -left-6 mt-1 h-3.5 w-3.5 rounded-full bg-accent-500/20 border-2 border-accent-400 shrink-0" />
                      <div className="bg-moso-850/80 border border-moso-800 rounded-lg p-3 w-full">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-moso-200 capitalize">
                            {(act.action_type || act.action || 'Activity').replace(/_/g, ' ')}
                          </span>
                          <span className="text-[10px] text-moso-500 font-mono">
                            {formatRelativeTime(act.created_at)}
                          </span>
                        </div>
                        <p className="text-moso-350 mt-1 text-[11px]">
                          {act.description || act.details || ''}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Note Creation / Editing Modal */}
      <Modal
        isOpen={isNoteModalOpen}
        onClose={() => setIsNoteModalOpen(false)}
        title={editingNoteId ? 'Edit Research Note' : 'New Research Note'}
        description="Record findings, methodologies, or experimental observations."
        maxWidth="md"
      >
        <div className="space-y-3.5 pt-2">
          <div>
            <label className="block text-[11px] font-semibold text-moso-300 mb-1">
              Note Title
            </label>
            <input
              type="text"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder="e.g. Validation Loss Anomaly in Epoch 42"
              className="w-full bg-moso-850 border border-moso-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-accent-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-moso-300 mb-1">
              Category
            </label>
            <div className="grid grid-cols-4 gap-2">
              {(['finding', 'methodology', 'experiment', 'note'] as const).map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setNoteCategory(cat)}
                  className={cn(
                    'px-2 py-1.5 rounded-md text-xs capitalize font-medium transition-colors cursor-pointer text-center',
                    noteCategory === cat
                      ? 'bg-accent-500 text-white font-semibold'
                      : 'bg-moso-850 text-moso-400 hover:text-white border border-moso-750'
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-moso-300 mb-1">
              Content (Markdown supported)
            </label>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              rows={6}
              placeholder="Detailed findings, mathematical equations, or experimental notes..."
              className="w-full bg-moso-850 border border-moso-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-accent-500 font-sans leading-relaxed"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-moso-800">
            <Button variant="ghost" onClick={() => setIsNoteModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSaveNote}>
              {editingNoteId ? 'Update Note' : 'Create Note'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Project Confirmation Modal */}
      <Modal
        isOpen={isDeletingProject}
        onClose={() => setIsDeletingProject(false)}
        title="Delete research workspace?"
        description={`This will permanently remove "${activeProject.name}", all its associated research papers, FTS5 indexed chunks, notes, activity logs, and project conversations from SQLite.`}
        maxWidth="sm"
      >
        <div className="flex justify-end gap-2.5 pt-4">
          <Button variant="ghost" onClick={() => setIsDeletingProject(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              if (activeProjectId) {
                await deleteProject(activeProjectId);
                setIsDeletingProject(false);
              }
            }}
          >
            Delete Workspace
          </Button>
        </div>
      </Modal>
    </div>
  );
};