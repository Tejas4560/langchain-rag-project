import React, { useState, useRef, useEffect } from 'react';
import { Upload, Send, Trash2, FileText, AlertCircle, CheckCircle, Loader, X, LogOut, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const API_URL = '/api';



function RAGInterface() {
    const [messages, setMessages] = useState([]);
    const [question, setQuestion] = useState('');
    const [loading, setLoading] = useState(false);
    const [fileUploaded, setFileUploaded] = useState(false);
    const [uploadStatus, setUploadStatus] = useState('');
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState('');
    const [isUploading, setIsUploading] = useState(false);

    const { token, logout, user } = useAuth();

    const chatEndRef = useRef(null);
    const fileInputRef = useRef(null);

    // Auto-scroll to bottom
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Clear error after 5 seconds
    useEffect(() => {
        if (error) {
            const timer = setTimeout(() => setError(''), 5000);
            return () => clearTimeout(timer);
        }
    }, [error]);

    // Initial load of files
    useEffect(() => {
        const fetchFiles = async () => {
            try {
                const response = await fetch(`${API_URL}/files`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setUploadedFiles(data.files || []);
                    if (data.files && data.files.length > 0) {
                        setFileUploaded(true);
                    }
                }
            } catch (e) {
                console.error("Failed to fetch files", e);
            }
        };
        if (token) {
            fetchFiles();
        }
    }, [token]);

    const uploadFile = async (e) => {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;

        // Validate file types
        const invalidFiles = files.filter(f => !f.name.toLowerCase().endsWith('.pdf'));
        if (invalidFiles.length > 0) {
            setError('Only PDF files are allowed');
            return;
        }

        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));

        setUploadStatus('Uploading files...');
        setUploadProgress(0);
        setIsUploading(true);
        // setFileUploaded(false); // Don't reset this immediately logic-wise if we have files already? 
        // Actually the logic implies if we upload new files we might want to reset chat context? 
        // existing code: setMessages([]);
        setMessages([]);
        setError('');

        try {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded * 100) / e.total);
                    setUploadProgress(percent);
                    setUploadStatus(
                        percent < 100 ? 'Uploading files...' : 'Processing and indexing documents...'
                    );
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    // Append new files to list? Or replace? 
                    // The backend returns all indexed files usually or just list. 
                    // Let's rely on what backend returns. Steps show backend returns "files": [list of all files] or list of uploaded?
                    // Backend code: "files": uploaded_filenames (just the new ones).
                    // But wait, the list_files endpoint returns all.
                    // Let's re-fetch files or append.
                    // For simplicity, let's just append or fetch.
                    // Backend response for upload includes "files": uploaded_filenames. 
                    // We should probably fetch all files again or just trust they are added.
                    // Let's just trust the response adds to existing?
                    // Actually existing code setUploadedFiles(response.files). 
                    // If response.files only implies NEW files, we lose old ones in UI.
                    // Let's fix this improvement: retrieve all files after upload.
                    fetchFiles(); // Call helper

                    setUploadStatus(`✓ ${response.files.length} file${response.files.length > 1 ? 's' : ''} uploaded successfully`);
                    setFileUploaded(true);
                    setUploadProgress(0);
                    setIsUploading(false);
                } else {
                    // Parse error
                    try {
                        const err = JSON.parse(xhr.responseText);
                        setError(err.detail || 'Upload failed');
                    } catch {
                        throw new Error('Upload failed');
                    }
                }
            });

            xhr.addEventListener('error', () => {
                setError('Upload failed. Please check your connection and try again.');
                setUploadStatus('');
                setUploadProgress(0);
                setIsUploading(false);
            });

            xhr.open('POST', `${API_URL}/upload`);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`); // Auth Header
            xhr.send(formData);

        } catch (err) {
            setError('Upload failed. Please try again.');
            setUploadStatus('');
            setUploadProgress(0);
            setIsUploading(false);
        }

        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const fetchFiles = async () => {
        try {
            const response = await fetch(`${API_URL}/files`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setUploadedFiles(data.files || []);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const sendQuestion = async () => {
        if (!question.trim() || loading) return;

        const userMessage = { sender: 'user', text: question };
        setMessages((prev) => [...prev, userMessage]);
        setQuestion('');
        setLoading(true);
        setError('');

        try {
            const response = await fetch(`${API_URL}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ question }),
            });

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            const data = await response.json();

            setMessages((prev) => [
                ...prev,
                {
                    sender: 'bot',
                    text: data.answer,
                    sources: data.sources || [],
                },
            ]);
        } catch (err) {
            if (err.message.includes('401')) {
                setError('Session expired. Please login again.');
                logout();
            } else {
                setError('Failed to get response. Please ensure the backend is running.');
                setMessages((prev) => [
                    ...prev,
                    {
                        sender: 'bot',
                        text: '⚠️ Unable to process your question. Please try again.',
                        isError: true,
                    },
                ]);
            }
        }

        setLoading(false);
    };

    const resetKnowledgeBase = async () => {
        if (!window.confirm('This will delete all uploaded documents and clear the knowledge base. Continue?')) {
            return;
        }

        setError('');
        try {
            const response = await fetch(`${API_URL}/reset`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Reset failed');
            }

            setMessages([]);
            setUploadedFiles([]);
            setFileUploaded(false);
            setUploadStatus('Knowledge base cleared successfully');
            setTimeout(() => setUploadStatus(''), 3000);
        } catch (err) {
            setError('Failed to reset knowledge base. Please try again.');
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="bg-white rounded-t-2xl shadow-lg p-6 border-b border-slate-200">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-3 rounded-xl shadow-md">
                                <FileText className="w-6 h-6 text-white" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold text-slate-800">RAG Document Assistant</h1>
                                <p className="text-sm text-slate-500">Upload PDFs and ask questions about your documents</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2 text-slate-600">
                                <User className="w-4 h-4" />
                                <span className="text-sm font-medium">{user?.username}</span>
                            </div>
                            <button
                                onClick={resetKnowledgeBase}
                                disabled={loading || isUploading}
                                className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed border border-red-200"
                                title="Reset Knowledge Base"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                            <button
                                onClick={logout}
                                className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors border border-slate-200"
                                title="Logout"
                            >
                                <LogOut className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="bg-red-50 border-l-4 border-red-500 p-4 flex items-start gap-3 animate-fadeIn">
                        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <p className="text-red-800 text-sm font-medium">{error}</p>
                        </div>
                        <button onClick={() => setError('')} className="text-red-500 hover:text-red-700">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* Upload Section */}
                <div className="bg-white shadow-lg p-6 border-b border-slate-200">
                    <div className="space-y-4">
                        <label className="block">
                            <div className="flex items-center justify-center w-full px-6 py-8 border-2 border-dashed border-slate-300 rounded-xl cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all group">
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf"
                                    multiple
                                    disabled={loading || isUploading}
                                    onChange={uploadFile}
                                    className="hidden"
                                />
                                <div className="text-center">
                                    <Upload className="w-10 h-10 text-slate-400 group-hover:text-blue-500 mx-auto mb-3 transition-colors" />
                                    <p className="text-sm font-medium text-slate-600 group-hover:text-blue-600">
                                        Click to upload PDF files
                                    </p>
                                    <p className="text-xs text-slate-400 mt-1">or drag and drop</p>
                                </div>
                            </div>
                        </label>

                        {/* Upload Progress */}
                        {uploadProgress > 0 && (
                            <div className="space-y-2">
                                <div className="flex justify-between text-sm text-slate-600">
                                    <span>{uploadStatus}</span>
                                    <span>{uploadProgress}%</span>
                                </div>
                                <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300 ease-out"
                                        style={{ width: `${uploadProgress}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Upload Status */}
                        {uploadStatus && uploadProgress === 0 && (
                            <div className={`flex items-center gap-2 text-sm p-3 rounded-lg ${uploadStatus.includes('✓')
                                    ? 'bg-green-50 text-green-700 border border-green-200'
                                    : 'bg-blue-50 text-blue-700 border border-blue-200'
                                }`}>
                                {uploadStatus.includes('✓') ? (
                                    <CheckCircle className="w-4 h-4" />
                                ) : (
                                    <Loader className="w-4 h-4 animate-spin" />
                                )}
                                <span>{uploadStatus}</span>
                            </div>
                        )}

                        {/* Uploaded Files List */}
                        {uploadedFiles.length > 0 && (
                            <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                                    <FileText className="w-4 h-4" />
                                    Indexed Documents ({uploadedFiles.length})
                                </h3>
                                <ul className="space-y-2">
                                    {uploadedFiles.map((file, i) => (
                                        <li key={i} className="text-sm text-slate-600 flex items-center gap-2 bg-white p-2 rounded border border-slate-200">
                                            <div className="w-2 h-2 bg-green-500 rounded-full" />
                                            {file}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>

                {/* Chat Section */}
                <div className="bg-white shadow-lg">
                    <div className="h-96 overflow-y-auto p-6 space-y-4">
                        {messages.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-center">
                                <div className="bg-slate-100 p-6 rounded-full mb-4">
                                    <FileText className="w-12 h-12 text-slate-400" />
                                </div>
                                <p className="text-slate-500 font-medium mb-2">No messages yet</p>
                                <p className="text-sm text-slate-400">
                                    {fileUploaded
                                        ? 'Ask a question about your uploaded documents'
                                        : 'Upload PDF files to get started'}
                                </p>
                            </div>
                        ) : (
                            messages.map((msg, idx) => (
                                <div
                                    key={idx}
                                    className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div
                                        className={`max-w-3xl rounded-2xl px-4 py-3 ${msg.sender === 'user'
                                                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white'
                                                : msg.isError
                                                    ? 'bg-red-50 text-red-900 border border-red-200'
                                                    : 'bg-slate-100 text-slate-800'
                                            }`}
                                    >
                                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>

                                        {msg.sources && msg.sources.length > 0 && (
                                            <div className="mt-3 pt-3 border-t border-slate-300">
                                                <p className="text-xs font-semibold mb-2 text-slate-600">Sources:</p>
                                                <ul className="space-y-1">
                                                    {msg.sources.map((src, i) => (
                                                        <li key={i} className="text-xs text-slate-600 flex items-center gap-2">
                                                            <div className="w-1 h-1 bg-slate-400 rounded-full" />
                                                            {src}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}

                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-slate-100 rounded-2xl px-4 py-3 flex items-center gap-2">
                                    <Loader className="w-4 h-4 animate-spin text-blue-500" />
                                    <span className="text-sm text-slate-600">Analyzing documents...</span>
                                </div>
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>
                </div>

                {/* Input Section */}
                <div className="bg-white rounded-b-2xl shadow-lg p-4 border-t border-slate-200">
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && sendQuestion()}
                            placeholder={
                                fileUploaded
                                    ? 'Ask a question about your documents...'
                                    : 'Upload PDFs to start asking questions'
                            }
                            disabled={!fileUploaded || loading || isUploading}
                            className="flex-1 px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-100 disabled:cursor-not-allowed text-sm"
                        />
                        <button
                            onClick={sendQuestion}
                            disabled={!fileUploaded || loading || !question.trim() || isUploading}
                            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium shadow-md hover:shadow-lg"
                        >
                            {loading ? (
                                <>
                                    <Loader className="w-4 h-4 animate-spin" />
                                    Thinking
                                </>
                            ) : (
                                <>
                                    <Send className="w-4 h-4" />
                                    Send
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>


        </div>
    );
}

export default RAGInterface;
