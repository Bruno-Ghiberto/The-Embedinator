'use client';

import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { getSettings, updateSettings } from '@/lib/api';
import type { Settings } from '@/lib/types';
import ProviderHub from '@/components/ProviderHub';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

// ─── SettingsPage ─────────────────────────────────────────────────────────────
//
// Vercel BP applied:
// - rerender-derived-state-no-effect: form isDirty/isLoading derived from RHF formState
//   during render — no useEffect needed
// - rendering-conditional-render: all conditionals use ternary, never &&
// - No optimistic UI: wait for API response before showing toast

export default function SettingsPage() {
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
      toast.success('Settings saved successfully');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save settings';
      toast.error(msg);
    }
  };

  const labelClass = 'mb-1 block text-sm font-medium text-foreground';
  const errorClass = 'mt-1 text-xs text-[var(--color-destructive)]';

  return (
    <main className="mx-auto max-w-3xl px-[var(--space-page)] py-8">
      <h1 className="mb-6 text-[length:var(--font-size-h1)] font-bold text-foreground">Settings</h1>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-10 w-72 rounded-md" />
          <Skeleton className="h-48 w-full rounded-lg" />
        </div>
      ) : (
      <Tabs defaultValue="providers">
        <TabsList>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="inference">Inference</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        {/* ── Providers Tab ───────────────────────────────────────────────── */}
        <TabsContent value="providers">
          <div className="mt-4">
            <ProviderHub />
          </div>
        </TabsContent>

        {/* ── Models Tab ──────────────────────────────────────────────────── */}
        <TabsContent value="models">
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Model Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-4"
                aria-label="Model settings form"
              >
                <div>
                  <label htmlFor="default_llm_model" className={labelClass}>
                    Default LLM Model
                  </label>
                  <Input
                    id="default_llm_model"
                    type="text"
                    disabled={isLoading}
                    {...register('default_llm_model', { required: 'LLM model is required' })}
                    placeholder="e.g. qwen2.5:7b"
                  />
                  {errors.default_llm_model ? (
                    <p className={errorClass} role="alert">
                      {errors.default_llm_model.message}
                    </p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="default_embed_model" className={labelClass}>
                    Default Embedding Model
                  </label>
                  <Input
                    id="default_embed_model"
                    type="text"
                    disabled={isLoading}
                    {...register('default_embed_model', { required: 'Embedding model is required' })}
                    placeholder="e.g. nomic-embed-text"
                  />
                  {errors.default_embed_model ? (
                    <p className={errorClass} role="alert">
                      {errors.default_embed_model.message}
                    </p>
                  ) : null}
                </div>

                <div className="flex items-center justify-end border-t border-border pt-4">
                  <Button type="submit" disabled={isSubmitting || isLoading}>
                    {isSubmitting ? 'Saving…' : 'Save Models'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Inference Tab ───────────────────────────────────────────────── */}
        <TabsContent value="inference">
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Inference Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-4"
                aria-label="Inference settings form"
              >
                <div>
                  <label htmlFor="confidence_threshold" className={labelClass}>
                    Confidence Threshold
                    <span className="ml-1 text-xs font-normal text-muted-foreground">(0 – 100)</span>
                  </label>
                  <Input
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
                  />
                  {errors.confidence_threshold ? (
                    <p className={errorClass} role="alert">
                      {errors.confidence_threshold.message}
                    </p>
                  ) : null}
                </div>

                <div className="flex items-center gap-3">
                  <input
                    id="groundedness_check_enabled"
                    type="checkbox"
                    disabled={isLoading}
                    {...register('groundedness_check_enabled')}
                    className="h-4 w-4 rounded border-border text-[var(--color-accent)] focus:ring-[var(--color-accent)] disabled:opacity-50"
                  />
                  <label htmlFor="groundedness_check_enabled" className="text-sm font-medium text-foreground">
                    Enable Groundedness Check
                  </label>
                </div>

                <div>
                  <label htmlFor="citation_alignment_threshold" className={labelClass}>
                    Citation Alignment Threshold
                    <span className="ml-1 text-xs font-normal text-muted-foreground">(0.0 – 1.0)</span>
                  </label>
                  <Input
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
                  />
                  {errors.citation_alignment_threshold ? (
                    <p className={errorClass} role="alert">
                      {errors.citation_alignment_threshold.message}
                    </p>
                  ) : null}
                </div>

                <div className="flex items-center justify-end border-t border-border pt-4">
                  <Button type="submit" disabled={isSubmitting || isLoading}>
                    {isSubmitting ? 'Saving…' : 'Save Inference'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── System Tab ──────────────────────────────────────────────────── */}
        <TabsContent value="system">
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Chunking Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-4"
                aria-label="System settings form"
              >
                <div>
                  <label htmlFor="parent_chunk_size" className={labelClass}>
                    Parent Chunk Size
                    <span className="ml-1 text-xs font-normal text-muted-foreground">(characters)</span>
                  </label>
                  <Input
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
                  />
                  {errors.parent_chunk_size ? (
                    <p className={errorClass} role="alert">
                      {errors.parent_chunk_size.message}
                    </p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="child_chunk_size" className={labelClass}>
                    Child Chunk Size
                    <span className="ml-1 text-xs font-normal text-muted-foreground">(characters)</span>
                  </label>
                  <Input
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
                  />
                  {errors.child_chunk_size ? (
                    <p className={errorClass} role="alert">
                      {errors.child_chunk_size.message}
                    </p>
                  ) : null}
                </div>

                <div className="flex items-center justify-between border-t border-border pt-4">
                  {isLoading ? (
                    <span className="text-xs text-muted-foreground">Loading current settings…</span>
                  ) : (
                    <span />
                  )}
                  <Button type="submit" disabled={isSubmitting || isLoading}>
                    {isSubmitting ? 'Saving…' : 'Save System'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      )}
    </main>
  );
}
