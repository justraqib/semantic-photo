import { useMemo } from 'react';
import PhotoCard from './PhotoCard';

function distributePhotos(photos, columnCount) {
  const columns = Array.from({ length: columnCount }, () => []);
  const heights = new Array(columnCount).fill(0);

  photos.forEach((photo, i) => {
    const shortestCol = heights.indexOf(Math.min(...heights));
    columns[shortestCol].push(photo);
    // Estimate height based on aspect ratio or use index-based variation
    const estimatedHeight = 200 + (i % 3) * 60;
    heights[shortestCol] += estimatedHeight;
  });

  return columns;
}

export default function PhotoGrid({ photos = [], onPhotoClick, renderActions }) {
  const columns2 = useMemo(() => distributePhotos(photos, 2), [photos]);
  const columns3 = useMemo(() => distributePhotos(photos, 3), [photos]);
  const columns4 = useMemo(() => distributePhotos(photos, 4), [photos]);
  const columns5 = useMemo(() => distributePhotos(photos, 5), [photos]);

  const renderColumn = (columnPhotos, colIdx) => (
    <div key={colIdx} className="flex flex-col gap-3">
      {columnPhotos.map((photo) => (
        <PhotoCard
          key={photo.id}
          photo={photo}
          onOpen={onPhotoClick}
          renderActions={renderActions}
        />
      ))}
    </div>
  );

  return (
    <>
      {/* 2 columns: mobile */}
      <div className="flex gap-3 md:hidden">
        {columns2.map((col, i) => renderColumn(col, i))}
      </div>
      {/* 3 columns: tablet */}
      <div className="hidden gap-3 md:flex lg:hidden">
        {columns3.map((col, i) => renderColumn(col, i))}
      </div>
      {/* 4 columns: desktop */}
      <div className="hidden gap-3 lg:flex xl:hidden">
        {columns4.map((col, i) => renderColumn(col, i))}
      </div>
      {/* 5 columns: wide desktop */}
      <div className="hidden gap-3 xl:flex">
        {columns5.map((col, i) => renderColumn(col, i))}
      </div>
    </>
  );
}
