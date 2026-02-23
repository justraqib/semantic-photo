import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import L from 'leaflet';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import { listMapPhotos } from '../api/photos';
import Lightbox from '../components/Lightbox';

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const DEFAULT_CENTER = [20, 0];

export default function MapPage() {
  const [selectedPhoto, setSelectedPhoto] = useState(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['map-photos'],
    queryFn: async () => {
      const response = await listMapPhotos();
      return response.data;
    },
  });

  const photos = data || [];
  const center = photos.length > 0 ? [photos[0].gps_lat, photos[0].gps_lng] : DEFAULT_CENTER;

  return (
    <div className="h-[calc(100vh-65px)] w-full p-4 md:p-6">
      {isLoading && <div className="h-full w-full animate-pulse rounded-xl bg-slate-200" />}

      {!isLoading && isError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          Unable to load map data right now.
        </div>
      )}

      {!isLoading && !isError && (
        <div className="h-full overflow-hidden rounded-xl border border-slate-200">
          <MapContainer center={center} zoom={photos.length > 0 ? 5 : 2} scrollWheelZoom className="h-full w-full">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {photos.map((photo) => (
              <Marker key={photo.id} position={[photo.gps_lat, photo.gps_lng]}>
                <Popup>
                  <div className="w-40">
                    {photo.thumbnail_url ? (
                      <img
                        src={photo.thumbnail_url}
                        alt="Photo location"
                        className="mb-2 h-24 w-full rounded object-cover"
                      />
                    ) : (
                      <div className="mb-2 flex h-24 w-full items-center justify-center rounded bg-slate-100 text-xs text-slate-500">
                        No preview
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => setSelectedPhoto(photo)}
                      className="w-full rounded bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-800"
                    >
                      Open in lightbox
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      )}

      <Lightbox
        photo={selectedPhoto}
        isOpen={!!selectedPhoto}
        onClose={() => setSelectedPhoto(null)}
        onNext={() => {}}
        onPrev={() => {}}
      />
    </div>
  );
}
