// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { PhotoUploadDropzone } from '../components/PhotoUploadDropzone';
import { bottomNavRoutes } from '@/app/layout/MenuBottomNav';
import { DEFAULT_MODE_ITEMS } from '@/app/layout/menuLayout';
import { PRODUCT_NAV_ROUTES } from '@/modules/productManifest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        'photoArchive.upload.take_photo': 'Tirar foto',
        'photoArchive.upload.choose_gallery': 'Escolher da galeria',
        'photoArchive.upload.hint': 'Solte fotos aqui',
        'photoArchive.upload.pick': 'Tirar ou escolher fotos',
      };
      return map[key] ?? opts?.defaultValue ?? key;
    },
    i18n: { language: 'pt-BR', changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}));

describe('Photo upload dual input (Camera + Gallery) and MenuBottomNav allowlist', () => {
  it('renders both camera (capture=environment) and gallery (without capture) inputs in PhotoUploadDropzone', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <PhotoUploadDropzone projectId="test-project" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const cameraInput = screen.getByTestId('photo-upload-camera-input') as HTMLInputElement;
    expect(cameraInput).toBeDefined();
    expect(cameraInput.getAttribute('type')).toBe('file');
    expect(cameraInput.getAttribute('accept')).toBe('image/*');
    expect(cameraInput.getAttribute('capture')).toBe('environment');
    expect(cameraInput.hasAttribute('multiple')).toBe(false);

    const galleryInput = screen.getByTestId('photo-upload-gallery-input') as HTMLInputElement;
    expect(galleryInput).toBeDefined();
    expect(galleryInput.getAttribute('type')).toBe('file');
    expect(galleryInput.getAttribute('accept')).toBe('image/*');
    expect(galleryInput.hasAttribute('capture')).toBe(false);
    expect(galleryInput.hasAttribute('multiple')).toBe(true);

    expect(screen.getByTestId('photo-upload-camera-button').textContent).toContain('Tirar foto');
    expect(screen.getByTestId('photo-upload-gallery-button').textContent).toContain('Escolher da galeria');
  });

  it('guarantees MenuBottomNav routes strictly belong to PRODUCT_NAV_ROUTES allowlist', () => {
    for (const [mode, routes] of Object.entries(DEFAULT_MODE_ITEMS)) {
      const bottom = bottomNavRoutes(routes);
      expect(bottom.length).toBeLessThanOrEqual(4);
      for (const r of bottom) {
        expect(PRODUCT_NAV_ROUTES.has(r)).toBe(true);
      }
    }
  });
});
