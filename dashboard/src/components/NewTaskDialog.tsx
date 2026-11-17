"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, X, Sparkles, Check, AlertCircle } from "lucide-react";
import { createTask } from "@/lib/api";

interface NewTaskDialogProps {
  isOpen: boolean;
  onClose: () => void;
  defaultAgent?: string;
}

export function NewTaskDialog({ isOpen, onClose, defaultAgent = "creative-pack" }: NewTaskDialogProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [agent, setAgent] = useState(defaultAgent);
  const [notifyLevel, setNotifyLevel] = useState<"final_only" | "milestones" | "everything">("milestones");
  const [maxUsd, setMaxUsd] = useState<number>(1.0);
  const [maxSteps, setMaxSteps] = useState<number>(25);

  const [criteria, setCriteria] = useState<{ description: string; type: string }[]>([
    { description: "All unit tests in sandbox exit with code 0", type: "command" },
    { description: "Brand voice adherence evaluated by independent judge model", type: "llm_judge" },
  ]);

  if (!isOpen) return null;

  const handleAddCriterion = () => {
    setCriteria([...criteria, { description: "", type: "command" }]);
  };

  const handleRemoveCriterion = (idx: number) => {
    setCriteria(criteria.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    try {
      setSubmitting(true);
      const computedTitle = title.trim() || prompt.slice(0, 60).trim() + "...";
      const { run } = await createTask({
        title: computedTitle,
        prompt: prompt.trim(),
        agent,
        notify_level: notifyLevel,
        budget: { max_usd: maxUsd, max_steps: maxSteps },
        criteria: criteria.filter((c) => c.description.trim().length > 0),
      });

      onClose();
      router.push(`/runs/${run.id}`);
    } catch (err) {
      console.error("Failed to create task:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl p-6 overflow-y-auto max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground text-base">New Agent Task</h3>
              <p className="text-xs text-muted-foreground">
                Declare task goal, assign agent, and establish upfront verification checks.
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">
              Task Prompt <span className="text-rose-500">*</span>
            </label>
            <textarea
              required
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Generate 3 Instagram ad variants for our oral weight-loss program, with compliant disclaimers and 1080x1080 graphics..."
              className="w-full text-sm px-3 py-2 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Target Agent
              </label>
              <select
                value={agent}
                onChange={(e) => setAgent(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="creative-pack">creative-pack (Healthcare Ads & Media)</option>
                <option value="analytics-agent">analytics-agent (Certified SQL & Metrics)</option>
                <option value="planner">planner (Task Decomposition)</option>
                <option value="executor">executor (General Sandbox Execution)</option>
                <option value="verifier">verifier (Independent Check Evaluator)</option>
                <option value="ops-agent">ops-agent (Recurring Monitoring & Sync)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">
                Notification Level
              </label>
              <select
                value={notifyLevel}
                onChange={(e) => setNotifyLevel(e.target.value as any)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="milestones">Milestones only (Start, Approval, Verdict)</option>
                <option value="everything">Everything (Every tool and model call)</option>
                <option value="final_only">Final result only</option>
              </select>
            </div>
          </div>

          {/* Budget Overrides */}
          <div className="grid grid-cols-2 gap-4 p-3 rounded-lg bg-secondary/30 border border-border">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                Max Budget (USD)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.01"
                value={maxUsd}
                onChange={(e) => setMaxUsd(parseFloat(e.target.value) || 0)}
                className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                Max Steps
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={maxSteps}
                onChange={(e) => setMaxSteps(parseInt(e.target.value) || 1)}
                className="w-full text-xs font-mono px-2.5 py-1.5 rounded border border-input bg-background text-foreground focus:outline-none"
              />
            </div>
          </div>

          {/* Acceptance Criteria Editor */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <span>Acceptance Criteria</span>
                <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.2 rounded">
                  verified before done
                </span>
              </label>
              <button
                type="button"
                onClick={handleAddCriterion}
                className="text-xs text-blue-500 hover:text-blue-400 font-medium inline-flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Check</span>
              </button>
            </div>

            <div className="space-y-2">
              {criteria.map((crit, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select
                    value={crit.type}
                    onChange={(e) => {
                      const updated = [...criteria];
                      updated[idx].type = e.target.value;
                      setCriteria(updated);
                    }}
                    className="w-32 text-xs px-2 py-1.5 rounded border border-input bg-background text-foreground focus:outline-none"
                  >
                    <option value="command">command</option>
                    <option value="artifact">artifact</option>
                    <option value="llm_judge">llm_judge</option>
                    <option value="http">http/browser</option>
                    <option value="grounded">grounded</option>
                    <option value="human">human</option>
                  </select>

                  <input
                    type="text"
                    value={crit.description}
                    onChange={(e) => {
                      const updated = [...criteria];
                      updated[idx].description = e.target.value;
                      setCriteria(updated);
                    }}
                    placeholder="Check description..."
                    className="flex-1 text-xs px-2.5 py-1.5 rounded border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none"
                  />

                  <button
                    type="button"
                    onClick={() => handleRemoveCriterion(idx)}
                    className="p-1 text-muted-foreground hover:text-rose-500"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Submit */}
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
              disabled={submitting || !prompt.trim()}
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg shadow-sm shadow-blue-500/30 transition-colors flex items-center gap-1.5"
            >
              {submitting ? "Starting Workflow..." : "Dispatch Task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
