import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignPeopleName,
  getPeopleGroupPhotos,
  listPeopleGroups,
  listPhotos,
  reindexPeopleGroups,
  removeFromPeopleGroup,
} from '../api/photos';

function PersonCard({ group, onOpen, onRename }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(group)}
      className="group rounded-2xl border border-surface-border bg-surface p-3 text-left transition-all duration-300 hover:border-accent/40 hover:bg-surface-hover"
    >
      <div className="mx-auto mb-2 h-24 w-24 overflow-hidden rounded-full border border-surface-border bg-background sm:h-28 sm:w-28">
        {group.photos?.[0]?.thumbnail_url ? (
          <img
            src={group.photos[0].thumbnail_url}
            alt={group.name || 'Unknown'}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-foreground-dim">?</div>
        )}
      </div>
      <p className="truncate text-sm font-semibold text-foreground">{group.name || 'Unknown'}</p>
      <p className="text-xs text-foreground-muted">{group.count} photos</p>
      <button
        type="button"
        className="mt-2 text-xs text-accent-light hover:text-accent"
        onClick={(event) => {
          event.stopPropagation();
          onRename(group);
        }}
      >
        Rename
      </button>
    </button>
  );
}

export default function PeoplePage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [openGroup, setOpenGroup] = useState(null);
  const [groupCursor, setGroupCursor] = useState(null);
  const [groupItems, setGroupItems] = useState([]);
  const [selectedInGroup, setSelectedInGroup] = useState(new Set());
  const [draftName, setDraftName] = useState('');
  const [renameGroup, setRenameGroup] = useState(null);
  const [isAddMode, setIsAddMode] = useState(false);
  const [addCursor, setAddCursor] = useState(null);
  const [addItems, setAddItems] = useState([]);

  const { data, isLoading } = useQuery({
    queryKey: ['people-groups'],
    queryFn: async () => (await listPeopleGroups()).data,
  });

  const assignMutation = useMutation({
    mutationFn: assignPeopleName,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['people-groups'] });
      await queryClient.invalidateQueries({ queryKey: ['search'] });
      if (openGroup) {
        setGroupCursor(null);
        setGroupItems([]);
      }
      setSelectedInGroup(new Set());
    },
  });
  const removeMutation = useMutation({
    mutationFn: removeFromPeopleGroup,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['people-groups'] });
      if (openGroup) {
        setGroupCursor(null);
        setGroupItems([]);
      }
      setSelectedInGroup(new Set());
    },
  });
  const reindexMutation = useMutation({
    mutationFn: () => reindexPeopleGroups({ full_reset: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['people-groups'] }),
  });

  const groups = data?.people || [];
  const namedGroups = groups.filter((group) => group.group_type === 'named');
  const unknownGroups = groups.filter((group) => group.group_type !== 'named');
  const normalizedQuery = query.trim().toLowerCase();
  const filteredNamed = normalizedQuery
    ? namedGroups.filter((group) => (group.name || '').toLowerCase().includes(normalizedQuery))
    : namedGroups;
  const filteredUnknown = normalizedQuery
    ? unknownGroups.filter((group) => (group.name || '').toLowerCase().includes(normalizedQuery))
    : unknownGroups;

  const selectedCount = selectedInGroup.size;

  const visibleGroupItems = useMemo(
    () => groupItems.filter((item) => !item._hidden),
    [groupItems]
  );

  const openPeopleGroup = async (group) => {
    setOpenGroup(group);
    setDraftName(group.name === 'Unknown' ? '' : group.name || '');
    setSelectedInGroup(new Set());
    setGroupItems([]);
    setGroupCursor(null);
    setIsAddMode(false);
    setAddItems([]);
    setAddCursor(null);

    const response = await getPeopleGroupPhotos(group.id, { limit: 120 });
    setGroupItems(response.data.items || []);
    setGroupCursor(response.data.next_cursor || null);
  };

  const loadMoreGroupItems = async () => {
    if (!openGroup || !groupCursor) return;
    const response = await getPeopleGroupPhotos(openGroup.id, { limit: 120, cursor: groupCursor });
    setGroupItems((prev) => [...prev, ...(response.data.items || [])]);
    setGroupCursor(response.data.next_cursor || null);
  };

  const startAddMode = async () => {
    setIsAddMode(true);
    setSelectedInGroup(new Set());
    const response = await listPhotos({ limit: 120 });
    setAddItems(response.data.items || []);
    setAddCursor(response.data.next_cursor || null);
  };

  const loadMoreAddItems = async () => {
    if (!addCursor) return;
    const response = await listPhotos({ limit: 120, cursor: addCursor });
    setAddItems((prev) => [...prev, ...(response.data.items || [])]);
    setAddCursor(response.data.next_cursor || null);
  };

  const toggleSelected = (photoId) => {
    const next = new Set(selectedInGroup);
    if (next.has(photoId)) next.delete(photoId);
    else next.add(photoId);
    setSelectedInGroup(next);
  };

  return (
    <div className="mx-auto max-w-[1400px] p-4 md:p-8">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">People</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Open person groups, confirm matches, remove wrong photos, and add more photos to named people.
          </p>
        </div>
        <div className="flex w-full gap-2 md:w-auto">
          <div className="w-full md:w-80">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search people"
              className="input-dark h-10 py-2.5"
            />
          </div>
          <button
            type="button"
            className="btn-secondary h-10 px-3 py-2 text-xs"
            onClick={() => reindexMutation.mutate()}
            disabled={reindexMutation.isPending}
          >
            {reindexMutation.isPending ? 'Rebuilding...' : 'Rebuild groups'}
          </button>
        </div>
      </div>

      {isLoading && <div className="text-sm text-foreground-muted">Loading people groups...</div>}

      {!isLoading && filteredNamed.length === 0 && filteredUnknown.length === 0 && (
        <div className="rounded-2xl border border-surface-border bg-surface p-8 text-center text-sm text-foreground-muted">
          No people groups found.
        </div>
      )}

      {filteredNamed.length > 0 && (
        <>
          <h2 className="mb-3 mt-1 text-sm font-semibold uppercase tracking-wide text-foreground-muted">Named people</h2>
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
            {filteredNamed.map((group) => (
              <PersonCard
                key={group.id}
                group={group}
                onOpen={openPeopleGroup}
                onRename={(g) => {
                  setRenameGroup(g);
                  setDraftName(g.name === 'Unknown' ? '' : g.name || '');
                }}
              />
            ))}
          </div>
        </>
      )}

      {filteredUnknown.length > 0 && (
        <>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-foreground-muted">Unknown groups</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
            {filteredUnknown.map((group) => (
              <PersonCard
                key={group.id}
                group={group}
                onOpen={openPeopleGroup}
                onRename={(g) => {
                  setRenameGroup(g);
                  setDraftName(g.name === 'Unknown' ? '' : g.name || '');
                }}
              />
            ))}
          </div>
        </>
      )}

      {renameGroup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-surface-border bg-background p-5">
            <h2 className="mb-2 text-lg font-semibold text-foreground">Rename person</h2>
            <input
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              className="input-dark"
              placeholder="Enter name"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setRenameGroup(null)}>Cancel</button>
              <button
                type="button"
                className="btn-primary"
                disabled={assignMutation.isPending}
                onClick={() =>
                  assignMutation.mutate(
                    {
                      photo_ids: (renameGroup.photos || []).map((photo) => photo.id),
                      name: draftName || 'Unknown',
                    },
                    { onSuccess: () => setRenameGroup(null) }
                  )
                }
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {openGroup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-6xl rounded-2xl border border-surface-border bg-background p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-foreground">{openGroup.name || 'Unknown'} group</h2>
                <p className="text-xs text-foreground-muted">
                  {isAddMode
                    ? 'Select photos to add into this person.'
                    : 'Select photos and confirm same person, or remove wrong photos.'}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!isAddMode && openGroup.name !== 'Unknown' && (
                  <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={startAddMode}>
                    Add photos
                  </button>
                )}
                <button
                  type="button"
                  className="btn-ghost px-3 py-1.5 text-xs"
                  onClick={() => {
                    const items = isAddMode ? addItems : visibleGroupItems;
                    setSelectedInGroup(new Set(items.map((photo) => photo.id)));
                  }}
                >
                  Select all
                </button>
                <button
                  type="button"
                  className="btn-ghost px-3 py-1.5 text-xs"
                  onClick={() => {
                    setOpenGroup(null);
                    setSelectedInGroup(new Set());
                    setIsAddMode(false);
                  }}
                >
                  Close
                </button>
              </div>
            </div>

            <div className="mb-4 max-h-[55vh] overflow-y-auto pr-1">
              <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
                {(isAddMode ? addItems : visibleGroupItems).map((photo) => (
                  <label key={photo.id} className="relative block cursor-pointer overflow-hidden rounded-lg">
                    <img src={photo.thumbnail_url} alt="" className="h-24 w-full object-cover md:h-28" />
                    <input
                      type="checkbox"
                      checked={selectedInGroup.has(photo.id)}
                      onChange={() => toggleSelected(photo.id)}
                      className="absolute left-1.5 top-1.5 h-4 w-4 accent-accent"
                    />
                    {selectedInGroup.has(photo.id) && (
                      <div className="pointer-events-none absolute inset-0 border-2 border-accent" />
                    )}
                  </label>
                ))}
              </div>
            </div>

            <div className="mb-3 flex gap-2">
              {!isAddMode && groupCursor && (
                <button type="button" className="btn-secondary text-xs" onClick={loadMoreGroupItems}>
                  Load more photos
                </button>
              )}
              {isAddMode && addCursor && (
                <button type="button" className="btn-secondary text-xs" onClick={loadMoreAddItems}>
                  Load more gallery photos
                </button>
              )}
              {isAddMode && (
                <button
                  type="button"
                  className="btn-ghost text-xs"
                  onClick={() => {
                    setIsAddMode(false);
                    setSelectedInGroup(new Set());
                  }}
                >
                  Back to group
                </button>
              )}
            </div>

            <div className="rounded-xl border border-surface-border bg-surface p-3">
              <p className="mb-2 text-xs text-foreground-muted">{selectedCount} selected</p>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={draftName}
                  onChange={(event) => setDraftName(event.target.value)}
                  className="input-dark min-w-48 py-2 text-sm"
                  placeholder="Person name"
                />
                <button
                  type="button"
                  className="btn-primary px-3 py-2 text-xs"
                  disabled={selectedCount === 0 || assignMutation.isPending}
                  onClick={() =>
                    assignMutation.mutate(
                      {
                        photo_ids: Array.from(selectedInGroup),
                        name: draftName || openGroup.name || 'Unknown',
                      },
                      {
                        onSuccess: async () => {
                          if (openGroup) {
                            const response = await getPeopleGroupPhotos(openGroup.id, { limit: 120 });
                            setGroupItems(response.data.items || []);
                            setGroupCursor(response.data.next_cursor || null);
                          }
                          setIsAddMode(false);
                        },
                      }
                    )
                  }
                >
                  {isAddMode ? 'Add selected to this person' : 'Confirm same person'}
                </button>
                {!isAddMode && (
                  <button
                    type="button"
                    className="btn-secondary px-3 py-2 text-xs"
                    disabled={selectedCount === 0 || removeMutation.isPending}
                    onClick={() =>
                      removeMutation.mutate(
                        { photo_ids: Array.from(selectedInGroup) },
                        {
                          onSuccess: () => {
                            setGroupItems((prev) =>
                              prev.map((item) =>
                                selectedInGroup.has(item.id) ? { ...item, _hidden: true } : item
                              )
                            );
                          },
                        }
                      )
                    }
                  >
                    Remove from group
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
