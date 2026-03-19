'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { getProviders, setProviderKey, deleteProviderKey } from '@/lib/api';
import type { Provider } from '@/lib/types';

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
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 capitalize">{provider.name}</h3>
          {provider.base_url !== null ? (
            <p className="mt-0.5 text-xs text-gray-500">{provider.base_url}</p>
          ) : null}
          <p className="mt-0.5 text-xs text-gray-400">{provider.model_count} model{provider.model_count !== 1 ? 's' : ''}</p>
        </div>

        {/* Indicators — is_active and has_key are independent */}
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              provider.is_active
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-500'
            }`}
            title={provider.is_active ? 'Provider is active' : 'Provider is inactive'}
          >
            {provider.is_active ? 'Active' : 'Inactive'}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              provider.has_key
                ? 'bg-blue-100 text-blue-700'
                : 'bg-yellow-100 text-yellow-700'
            }`}
            title={provider.has_key ? 'API key is stored' : 'No API key stored'}
          >
            {provider.has_key ? 'Key set' : 'No key'}
          </span>
        </div>
      </div>

      {/* Key display and management */}
      <div className="mt-3">
        {provider.has_key ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value="••••••••"
              readOnly
              aria-label={`Masked API key for ${provider.name}`}
              className="flex-1 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-500 cursor-not-allowed"
            />
            <button
              onClick={onDelete}
              disabled={isLoading}
              aria-label={`Delete API key for ${provider.name}`}
              className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              {isLoading ? 'Deleting…' : 'Delete key'}
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="password"
              value={keyInput}
              onChange={(e) => onKeyInputChange(e.target.value)}
              placeholder={`Enter ${provider.name} API key`}
              aria-label={`API key input for ${provider.name}`}
              className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={onSave}
              disabled={isLoading || !keyInput.trim()}
              aria-label={`Save API key for ${provider.name}`}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving…' : 'Save key'}
            </button>
          </div>
        )}

        {error ? (
          <p className="mt-1 text-xs text-red-600" role="alert">{error}</p>
        ) : null}
      </div>
    </div>
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
          <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-100" />
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
