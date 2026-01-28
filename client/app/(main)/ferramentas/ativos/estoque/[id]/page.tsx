import { AssetDetailContent } from './AssetDetailContent';

// Generate static params for export (required for output: export)
// Returns placeholder ID - actual assets are loaded client-side
export async function generateStaticParams(): Promise<{ id: string }[]> {
  // For static export, we need at least one path
  // The actual asset loading happens client-side
  return [{ id: '_' }];
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function AssetDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <AssetDetailContent id={id} />;
}
