import BlogView from "@/components/blog-view";
export default async function BlogPage({ params }: { params: Promise<{ id: string }> }) { return <BlogView id={(await params).id} />; }
