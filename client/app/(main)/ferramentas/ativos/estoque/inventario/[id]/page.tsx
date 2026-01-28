import { CampaignDetailContent } from './CampaignDetailContent';

// Generate static params for export (required for output: export)
// Returns placeholder ID - actual campaigns are loaded client-side
export async function generateStaticParams(): Promise<{ id: string }[]> {
  // For static export, we need at least one path
  // The actual campaign loading happens client-side
  return [{ id: '_' }];
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function CampaignDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <CampaignDetailContent id={id} />;
}
