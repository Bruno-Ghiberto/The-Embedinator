'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Eye, EyeOff } from 'lucide-react';
import { getProviders, setProviderKey, deleteProviderKey } from '@/lib/api';
import type { Provider } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/components/ui/tooltip';

// ─── ProviderRow ─────────────────────────────────────────────────────────────
// Defined outside ProviderHub to avoid re-creating the component on every render
// (Vercel BP: rerender-no-inline-components)

interface ProviderRowProps {
  provider: Provider;
  keyInput: string;
  error: string;
  isLoading: boolean;
  onKeyInputChange: (value: string) => void;
  onSave: () => void;
  onDelete: () => void;
}

function ProviderRow({
  provider,
  keyInput,
  error,
  isLoading,
  onKeyInputChange,
  onSave,
  onDelete,
}: ProviderRowProps) {
  const [showKey, setShowKey] = useState(false);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-block h-2.5 w-2.5 rounded-full',
                provider.has_key
                  ? 'bg-success'
                  : 'bg-muted-foreground'
              )}
              aria-label={provider.has_key ? 'API key configured' : 'No API key'}
            />
            <CardTitle className="capitalize">{provider.name}</CardTitle>
          </div>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              provider.is_active
                ? 'bg-success/10 text-success'
                : 'text-muted-foreground bg-muted'
            )}
          >
            {provider.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        {provider.base_url !== null ? (
          <p className="text-xs text-muted-foreground">{provider.base_url}</p>
        ) : null}
        <p className="text-xs text-muted-foreground">
          {provider.model_count} model{provider.model_count !== 1 ? 's' : ''}
        </p>
      </CardHeader>

      <CardContent>
        {provider.has_key ? (
          <div className="flex items-center gap-2">
            <Input
              type="text"
              value="••••••••"
              readOnly
              aria-label={`Masked API key for ${provider.name}`}
              className="flex-1 cursor-not-allowed"
            />
            <Button
              variant="destructive"
              size="sm"
              onClick={onDelete}
              disabled={isLoading}
              aria-label={`Delete API key for ${provider.name}`}
            >
              {isLoading ? 'Deleting…' : 'Delete key'}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Input
                type={showKey ? 'text' : 'password'}
                value={keyInput}
                onChange={(e) => onKeyInputChange(e.target.value)}
                placeholder={`Enter ${provider.name} API key`}
                aria-label={`API key input for ${provider.name}`}
                className="pr-9"
              />
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="absolute right-1.5 top-1/2 -translate-y-1/2"
                      onClick={() => setShowKey((prev) => !prev)}
                      aria-label={showKey ? 'Hide API key' : 'Show API key'}
                    />
                  }
                >
                  {showKey ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                </TooltipTrigger>
                <TooltipContent>{showKey ? 'Hide API key' : 'Show API key'}</TooltipContent>
              </Tooltip>
            </div>
            <Button
              size="sm"
              onClick={onSave}
              disabled={isLoading || !keyInput.trim()}
              aria-label={`Save API key for ${provider.name}`}
            >
              {isLoading ? 'Saving…' : 'Save key'}
            </Button>
          </div>
        )}

        {error ? (
          <p className="mt-1 text-xs text-destructive" role="alert">{error}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ─── ProviderHub ──────────────────────────────────────────────────────────────

// ProviderHub fetches its own data — no props required.
// revalidateOnFocus: false because provider list changes slowly
// (Vercel BP: client-swr-dedup)
export default function ProviderHub() {
  const { data: providers, mutate } = useSWR<Provider[]>(
    '/api/providers',
    getProviders,
    { revalidateOnFocus: false },
  );

  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loadingStates, setLoadingStates] = useState<Record<string, boolean>>({});

  const handleSaveKey = async (name: string) => {
    const key = keyInputs[name]?.trim();
    if (!key) {
      setErrors((prev) => ({ ...prev, [name]: 'API key cannot be empty' }));
      return;
    }
    setLoadingStates((prev) => ({ ...prev, [name]: true }));
    try {
      await setProviderKey(name, key);
      // Clear input on success — functional setState avoids stale closure
      setKeyInputs((prev) => ({ ...prev, [name]: '' }));
      setErrors((prev) => ({ ...prev, [name]: '' }));
      await mutate();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save key';
      setErrors((prev) => ({ ...prev, [name]: msg }));
    } finally {
      setLoadingStates((prev) => ({ ...prev, [name]: false }));
    }
  };

  const handleDeleteKey = async (name: string) => {
    setLoadingStates((prev) => ({ ...prev, [name]: true }));
    setErrors((prev) => ({ ...prev, [name]: '' }));
    try {
      await deleteProviderKey(name);
      await mutate();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete key';
      setErrors((prev) => ({ ...prev, [name]: msg }));
    } finally {
      setLoadingStates((prev) => ({ ...prev, [name]: false }));
    }
  };

  if (!providers) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {providers.map((provider) => (
        <ProviderRow
          key={provider.name}
          provider={provider}
          keyInput={keyInputs[provider.name] ?? ''}
          error={errors[provider.name] ?? ''}
          isLoading={loadingStates[provider.name] ?? false}
          onKeyInputChange={(val) =>
            setKeyInputs((prev) => ({ ...prev, [provider.name]: val }))
          }
          onSave={() => handleSaveKey(provider.name)}
          onDelete={() => handleDeleteKey(provider.name)}
        />
      ))}
    </div>
  );
}
