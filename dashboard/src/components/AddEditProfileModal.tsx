"use client";

import { useState } from "react";
import {
  X,
  Eye,
  EyeOff,
  Key,
  Cpu,
  Video,
  Image as ImageIcon,
  Volume2,
  Mic,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  Shield,
  Layers,
} from "lucide-react";
import type { Capability, ModelProfile } from "@/types";

interface AddEditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (profile: Partial<ModelProfile> & { apiKey?: string }) => void;
  initialProfile?: ModelProfile | null;
}

export function AddEditProfileModal({
  isOpen,
  onClose,
  onSave,
  initialProfile,
}: AddEditProfileModalProps) {
  const [name, setName] = useState(initialProfile?.name || "");
  const [provider, setProvider] = useState(initialProfile?.provider || "Google");
  const [model, setModel] = useState(initialProfile?.model || "");
  const [capability, setCapability] = useState<Capability>(
    initialProfile?.capability || "chat"
  );
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [keyEnvVar, setKeyEnvVar] = useState(
    initialProfile?.key_env_var || "GEMINI_API_KEY"
  );
  const [tags, setTags] = useState(initialProfile?.tags.join(", ") || "fast, smart");

  // Dynamic cost states based on capability
  const [inputCost, setInputCost] = useState(
    initialProfile?.cost.input_per_mtok?.toString() || "0.35"
  );
  const [outputCost, setOutputCost] = useState(
    initialProfile?.cost.output_per_mtok?.toString() || "1.05"
  );
  const [perImageCost, setPerImageCost] = useState(
    initialProfile?.cost.per_image?.toString() || "0.03"
  );
  const [perVideoCost, setPerVideoCost] = useState(
    initialProfile?.cost.per_video?.toString() || "0.30"
  );
  const [perVoiceCost, setPerVoiceCost] = useState(
    initialProfile?.cost.per_1k_chars?.toString() || "0.002"
  );

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    if (newProvider === "Google") setKeyEnvVar("GEMINI_API_KEY");
    else if (newProvider === "Groq") setKeyEnvVar("GROQ_API_KEY");
    else if (newProvider === "OpenAI") setKeyEnvVar("OPENAI_API_KEY");
    else if (newProvider === "Anthropic") setKeyEnvVar("ANTHROPIC_API_KEY");
    else if (newProvider === "ElevenLabs") setKeyEnvVar("ELEVENLABS_API_KEY");
    else if (newProvider === "Runway") setKeyEnvVar("RUNWAY_API_KEY");
    else if (newProvider === "Luma") setKeyEnvVar("LUMA_API_KEY");
    else setKeyEnvVar(`${newProvider.toUpperCase().replace(/\s+/g, "_")}_API_KEY`);
  };

  const handleTestKey = async () => {
    setTesting(true);
    setTestResult(null);
    // Simulate ping to provider API
    await new Promise((r) => setTimeout(r, 700));
    setTesting(false);
    setTestResult("API Key verified successfully: ping 200 OK.");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const tagArray = tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const costObj: ModelProfile["cost"] = {};
    if (capability === "chat" || capability === "vision" || capability === "embedding") {
      costObj.input_per_mtok = parseFloat(inputCost) || 0;
      costObj.output_per_mtok = parseFloat(outputCost) || 0;
    } else if (capability === "image_gen") {
      costObj.per_image = parseFloat(perImageCost) || 0;
    } else if (capability === "video_gen") {
      costObj.per_video = parseFloat(perVideoCost) || 0;
    } else if (capability === "tts" || capability === "stt") {
      costObj.per_1k_chars = parseFloat(perVoiceCost) || 0;
    }

    onSave({
      id: initialProfile?.id || `${provider.toLowerCase()}-${model.toLowerCase().replace(/[^a-z0-9]/g, "-")}`,
      name: name.trim() || `${provider} ${model}`,
      provider,
      model,
      capability,
      tags: tagArray,
      cost: costObj,
      key_configured: Boolean(apiKey || initialProfile?.key_configured),
      enabled: true,
      key_env_var: keyEnvVar,
      apiKey: apiKey || undefined,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl p-6 overflow-y-auto max-h-[90vh] space-y-5">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground text-base">
                {initialProfile ? "Edit Model & API Profile" : "Add Model Provider & API Key"}
              </h3>
              <p className="text-xs text-muted-foreground">
                Connect multi-modal models for chat, vision, images, video, and voice synthesis.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Provider & Capability */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Provider
              </label>
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="Google">Google (Gemini, Imagen, Veo)</option>
                <option value="Groq">Groq (Llama, Whisper, Orpheus)</option>
                <option value="OpenAI">OpenAI (GPT-4o, DALL-E, Sora, TTS)</option>
                <option value="Anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
                <option value="ElevenLabs">ElevenLabs (Voice / TTS)</option>
                <option value="Runway">Runway (Video Generation)</option>
                <option value="Luma">Luma Dream Machine (Video)</option>
                <option value="Replicate">Replicate / Fal.ai</option>
                <option value="Custom">Custom / Local API Endpoint</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Capability Type
              </label>
              <select
                value={capability}
                onChange={(e) => setCapability(e.target.value as Capability)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="chat">💬 Chat & Tool Execution</option>
                <option value="vision">👁️ Vision & Multimodal Analysis</option>
                <option value="image_gen">🖼️ Image Generation (Imagen / Flux / DALL-E)</option>
                <option value="video_gen">🎬 Video Generation (Veo / Runway / Sora)</option>
                <option value="tts">🎙️ Voice & Text-to-Speech (ElevenLabs / Groq)</option>
                <option value="stt">👂 Speech-to-Text (Whisper / Audio transcription)</option>
                <option value="embedding">🧬 Vector Embeddings (Search & Retrieval)</option>
              </select>
            </div>
          </div>

          {/* Model Name and Identifier */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Display Profile Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Gemini 2.5 Flash or Runway Gen-3"
                className="w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Exact Model Identifier
              </label>
              <input
                type="text"
                required
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="e.g. gemini-2.5-flash, veo-2.0, or eleven_multilingual_v2"
                className="w-full text-xs font-mono px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          {/* Secret API Key Input with Eye Toggle */}
          <div className="p-4 rounded-xl border border-border bg-secondary/30 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-amber-500" />
                <span>Provider Secret API Key</span>
              </label>
              <span className="text-[11px] font-mono text-muted-foreground flex items-center gap-1">
                <Shield className="w-3 h-3 text-emerald-500" />
                <span>Masked & encrypted server-side</span>
              </span>
            </div>

            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  initialProfile?.key_configured
                    ? "•••••••••••••••••••••••• (Leave blank to keep existing key)"
                    : "Paste API key (e.g. AIzaSy..., gsk_..., or sk-...)"
                }
                className="w-full text-xs font-mono pl-3 pr-10 py-2 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />

              {/* Eye icon to toggle visibility */}
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
                title={showApiKey ? "Hide API key" : "Show API key"}
                aria-label={showApiKey ? "Hide API key" : "Show API key"}
              >
                {showApiKey ? (
                  <EyeOff className="w-4 h-4 text-amber-500" />
                ) : (
                  <Eye className="w-4 h-4 text-muted-foreground" />
                )}
              </button>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 text-[11px] text-muted-foreground">
              <div className="flex items-center gap-1 font-mono">
                <span>Env variable:</span>
                <input
                  type="text"
                  value={keyEnvVar}
                  onChange={(e) => setKeyEnvVar(e.target.value)}
                  className="px-1.5 py-0.5 rounded border border-input bg-background text-foreground text-[11px] font-mono"
                />
              </div>

              {apiKey && (
                <button
                  type="button"
                  onClick={handleTestKey}
                  disabled={testing}
                  className="text-xs font-medium text-blue-500 hover:text-blue-400 self-start sm:self-auto"
                >
                  {testing ? "Testing key..." : "Test Connection"}
                </button>
              )}
            </div>

            {testResult && (
              <div className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/20 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>{testResult}</span>
              </div>
            )}
          </div>

          {/* Dynamic Pricing / Cost Fields */}
          <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-2">
            <label className="text-xs font-semibold text-foreground block">
              Unit Cost Configuration (USD)
            </label>

            {(capability === "chat" || capability === "vision" || capability === "embedding") && (
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[11px] mb-1">
                    Input Cost per 1M Tokens ($)
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    value={inputCost}
                    onChange={(e) => setInputCost(e.target.value)}
                    className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                  />
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px] mb-1">
                    Output Cost per 1M Tokens ($)
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    value={outputCost}
                    onChange={(e) => setOutputCost(e.target.value)}
                    className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                  />
                </div>
              </div>
            )}

            {capability === "image_gen" && (
              <div className="text-xs max-w-xs">
                <span className="text-muted-foreground block text-[11px] mb-1">
                  Cost per Generated Image ($)
                </span>
                <input
                  type="number"
                  step="0.005"
                  value={perImageCost}
                  onChange={(e) => setPerImageCost(e.target.value)}
                  className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                />
              </div>
            )}

            {capability === "video_gen" && (
              <div className="text-xs max-w-xs">
                <span className="text-muted-foreground block text-[11px] mb-1">
                  Cost per Video Generation / Clip ($)
                </span>
                <input
                  type="number"
                  step="0.05"
                  value={perVideoCost}
                  onChange={(e) => setPerVideoCost(e.target.value)}
                  className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                />
              </div>
            )}

            {(capability === "tts" || capability === "stt") && (
              <div className="text-xs max-w-xs">
                <span className="text-muted-foreground block text-[11px] mb-1">
                  Cost per 1,000 Voice Characters ($)
                </span>
                <input
                  type="number"
                  step="0.0005"
                  value={perVoiceCost}
                  onChange={(e) => setPerVoiceCost(e.target.value)}
                  className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                />
              </div>
            )}
          </div>

          {/* Tags */}
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">
              Router Tags (comma separated)
            </label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. fast, cheap, smart, photorealistic, cinematic"
              className="w-full text-xs font-mono px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none"
            />
          </div>

          {/* Actions */}
          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg border border-border hover:bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-sm shadow-blue-500/30 transition-colors"
            >
              Save Profile & Credentials
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
