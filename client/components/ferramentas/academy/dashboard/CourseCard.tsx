// =============================================================================
// Course Card - Faiston Academy Dashboard
// =============================================================================
// Displays a course thumbnail with title and category.
// Used in course carousels and listings.
// =============================================================================

'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Play } from 'lucide-react';

export interface Course {
  id: string;
  title: string;
  category: string;
  thumbnail: string;
  progress?: number;
  episodeCount?: number;
}

interface CourseCardProps {
  course: Course;
  href?: string;
}

export function CourseCard({ course, href }: CourseCardProps) {
  const cardContent = (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className="w-[240px] flex-shrink-0 cursor-pointer"
    >
      <div className="relative w-full h-[140px] rounded-xl overflow-hidden group">
        <img
          src={course.thumbnail}
          alt={course.title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
        {/* Overlay gradient */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent group-hover:from-black/70 transition-all" />

        {/* Play button on hover */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-12 h-12 rounded-full bg-[var(--faiston-magenta-mid,#C31B8C)]/90 flex items-center justify-center">
            <Play className="w-5 h-5 text-white fill-white ml-0.5" />
          </div>
        </div>

        {/* Progress bar (if available) */}
        {course.progress !== undefined && course.progress > 0 && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20">
            <div
              className="h-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)]"
              style={{ width: `${course.progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Course info */}
      <div className="mt-3">
        <h3 className="text-sm font-semibold text-white line-clamp-2 leading-tight">
          {course.title}
        </h3>
        <div className="flex items-center gap-2 mt-1">
          <p className="text-xs text-white/50">{course.category}</p>
          {course.episodeCount && (
            <>
              <span className="text-white/30">•</span>
              <p className="text-xs text-white/50">
                {course.episodeCount} {course.episodeCount === 1 ? 'episodio' : 'episodios'}
              </p>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );

  if (href) {
    return (
      <Link href={href} className="block">
        {cardContent}
      </Link>
    );
  }

  return cardContent;
}
