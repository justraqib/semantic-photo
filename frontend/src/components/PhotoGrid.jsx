import PhotoCard from './PhotoCard';

export default function PhotoGrid({ photos = [], onPhotoClick, renderActions }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {photos.map((photo) => (
        <PhotoCard
          key={photo.id}
          photo={photo}
          onOpen={onPhotoClick}
          renderActions={renderActions}
        />
      ))}
    </div>
  );
}
