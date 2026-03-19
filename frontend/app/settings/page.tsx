'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { getSettings, updateSettings } from '@/lib/api';
import type { Settings } from '@/lib/types';
import Toast from '@/components/Toast';
import ProviderHub from '@/components/ProviderHub';

// ─── SettingsPage ─────────────────────────────────────────────────────────────
//
// Vercel BP applied:
// - rerender-derived-state-no-effect: form isDirty/isLoading derived from RHF formState
//   during render — no useEffect needed
// - rendering-conditional-render: all conditionals use ternary, never &&
// - No optimistic UI: wait for API response before showing toast

export default function SettingsPage() {
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Async defaultValues: React Hook Form fetches settings on mount, sets formState.isLoading=true
  // while pending. No separate useState + useEffect fetch pattern needed.
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isLoading },
  } = useForm<Settings>({
    defaultValues: async () => {
      return getSettings();
    },
  });

  const onSubmit = async (data: Settings) => {
    // No optimistic UI — wait for response, then show toast
    try {
      await updateSettings(data);
      setToast({ message: 'Settings saved', type: 'success' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save settings';
      setToast({ message: msg, type: 'error' });
    }
  };

  const fieldClass =
    'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400';
  const labelClass = 'mb-1 block text-sm font-medium text-gray-700';
  const errorClass = 'mt-1 text-xs text-red-600';

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Settings</h1>

      {/* Settings Form — all 7 fields */}
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
        aria-label="Settings form"
      >
        {/* ── Model Settings ─────────────────────────────────────────────── */}
        <section aria-labelledby="model-settings-heading">
          <h2
            id="model-settings-heading"
            className="mb-4 text-base font-semibold text-gray-800"
          >
            Model Settings
          </h2>

          <div className="space-y-4">
            {/* Field 1: default_llm_model */}
            <div>
              <label htmlFor="default_llm_model" className={labelClass}>
                Default LLM Model
              </label>
              <input
                id="default_llm_model"
                type="text"
                disabled={isLoading}
                {...register('default_llm_model', { required: 'LLM model is required' })}
                className={fieldClass}
                placeholder="e.g. qwen2.5:7b"
              />
              {errors.default_llm_model ? (
                <p className={errorClass} role="alert">
                  {errors.default_llm_model.message}
                </p>
              ) : null}
            </div>

            {/* Field 2: default_embed_model */}
            <div>
              <label htmlFor="default_embed_model" className={labelClass}>
                Default Embedding Model
              </label>
              <input
                id="default_embed_model"
                type="text"
                disabled={isLoading}
                {...register('default_embed_model', { required: 'Embedding model is required' })}
                className={fieldClass}
                placeholder="e.g. nomic-embed-text"
              />
              {errors.default_embed_model ? (
                <p className={errorClass} role="alert">
                  {errors.default_embed_model.message}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {/* ── Quality Settings ────────────────────────────────────────────── */}
        <section aria-labelledby="quality-settings-heading">
          <h2
            id="quality-settings-heading"
            className="mb-4 text-base font-semibold text-gray-800"
          >
            Quality Settings
          </h2>

          <div className="space-y-4">
            {/* Field 3: confidence_threshold (integer 0-100) */}
            <div>
              <label htmlFor="confidence_threshold" className={labelClass}>
                Confidence Threshold
                <span className="ml-1 text-xs font-normal text-gray-500">(0 – 100)</span>
              </label>
              <input
                id="confidence_threshold"
                type="number"
                min={0}
                max={100}
                step={1}
                disabled={isLoading}
                {...register('confidence_threshold', {
                  required: 'Confidence threshold is required',
                  min: { value: 0, message: 'Minimum is 0' },
                  max: { value: 100, message: 'Maximum is 100' },
                  valueAsNumber: true,
                })}
                className={fieldClass}
              />
              {errors.confidence_threshold ? (
                <p className={errorClass} role="alert">
                  {errors.confidence_threshold.message}
                </p>
              ) : null}
            </div>

            {/* Field 4: groundedness_check_enabled (boolean) */}
            <div className="flex items-center gap-3">
              <input
                id="groundedness_check_enabled"
                type="checkbox"
                disabled={isLoading}
                {...register('groundedness_check_enabled')}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
              />
              <label htmlFor="groundedness_check_enabled" className="text-sm font-medium text-gray-700">
                Enable Groundedness Check
              </label>
            </div>

            {/* Field 5: citation_alignment_threshold (float) */}
            <div>
              <label htmlFor="citation_alignment_threshold" className={labelClass}>
                Citation Alignment Threshold
                <span className="ml-1 text-xs font-normal text-gray-500">(0.0 – 1.0)</span>
              </label>
              <input
                id="citation_alignment_threshold"
                type="number"
                min={0}
                max={1}
                step={0.01}
                disabled={isLoading}
                {...register('citation_alignment_threshold', {
                  required: 'Citation alignment threshold is required',
                  min: { value: 0, message: 'Minimum is 0' },
                  max: { value: 1, message: 'Maximum is 1' },
                  valueAsNumber: true,
                })}
                className={fieldClass}
              />
              {errors.citation_alignment_threshold ? (
                <p className={errorClass} role="alert">
                  {errors.citation_alignment_threshold.message}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {/* ── Chunking Settings ───────────────────────────────────────────── */}
        <section aria-labelledby="chunking-settings-heading">
          <h2
            id="chunking-settings-heading"
            className="mb-4 text-base font-semibold text-gray-800"
          >
            Chunking Settings
          </h2>

          <div className="space-y-4">
            {/* Field 6: parent_chunk_size */}
            <div>
              <label htmlFor="parent_chunk_size" className={labelClass}>
                Parent Chunk Size
                <span className="ml-1 text-xs font-normal text-gray-500">(characters)</span>
              </label>
              <input
                id="parent_chunk_size"
                type="number"
                min={1}
                step={1}
                disabled={isLoading}
                {...register('parent_chunk_size', {
                  required: 'Parent chunk size is required',
                  min: { value: 1, message: 'Minimum is 1' },
                  valueAsNumber: true,
                })}
                className={fieldClass}
              />
              {errors.parent_chunk_size ? (
                <p className={errorClass} role="alert">
                  {errors.parent_chunk_size.message}
                </p>
              ) : null}
            </div>

            {/* Field 7: child_chunk_size */}
            <div>
              <label htmlFor="child_chunk_size" className={labelClass}>
                Child Chunk Size
                <span className="ml-1 text-xs font-normal text-gray-500">(characters)</span>
              </label>
              <input
                id="child_chunk_size"
                type="number"
                min={1}
                step={1}
                disabled={isLoading}
                {...register('child_chunk_size', {
                  required: 'Child chunk size is required',
                  min: { value: 1, message: 'Minimum is 1' },
                  valueAsNumber: true,
                })}
                className={fieldClass}
              />
              {errors.child_chunk_size ? (
                <p className={errorClass} role="alert">
                  {errors.child_chunk_size.message}
                </p>
              ) : null}
            </div>
          </div>
        </section>

        {/* ── Submit ──────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between border-t border-gray-100 pt-4">
          {isLoading ? (
            <span className="text-xs text-gray-400">Loading current settings…</span>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="rounded-md bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {isSubmitting ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </form>

      {/* ── Provider Hub ─────────────────────────────────────────────────── */}
      <section className="mt-10" aria-labelledby="providers-heading">
        <h2 id="providers-heading" className="mb-4 text-xl font-bold text-gray-900">
          API Keys & Providers
        </h2>
        <ProviderHub />
      </section>

      {/* ── Toast notification ───────────────────────────────────────────── */}
      {toast !== null ? (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      ) : null}
    </main>
  );
}
