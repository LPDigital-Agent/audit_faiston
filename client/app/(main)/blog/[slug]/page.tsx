import Link from "next/link";
import { getAllPostSlugs, getPostBySlug } from "@/mocks/blog-mock-data";
import { BlogArticleContent } from "./BlogArticleContent";

/**
 * Blog Article Page - Server Component wrapper
 *
 * This is a Server Component that provides static params for export
 * and delegates rendering to the client component.
 */

// Generate static params for all blog posts (required for output: export)
export function generateStaticParams() {
  const slugs = getAllPostSlugs();
  return slugs.map((slug) => ({ slug }));
}

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default async function BlogArticlePage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPostBySlug(slug);

  if (!post) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-text-primary mb-4">
            Artigo nao encontrado
          </h1>
          <p className="text-text-secondary mb-6">
            O artigo que voce procura nao existe ou foi removido.
          </p>
          <Link
            href="/blog"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-magenta-mid/20 border border-magenta-mid/40 text-magenta-light hover:bg-magenta-mid/30 transition-colors"
          >
            Voltar para Blog
          </Link>
        </div>
      </div>
    );
  }

  return <BlogArticleContent post={post} />;
}
