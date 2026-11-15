"use client";

import { useParams, useRouter } from "next/navigation";
import FarmForm from "@/components/FarmForm";
import { ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import type { Farm } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

export default function EditFarmPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { reload } = useFarm();
  const farm = useAsync(() => api.get<Farm>(`/api/farms/${id}`), [id]);
  return (
    <div>
      <PageHeader title="Edit farm" />
      {farm.loading ? <Loading /> : farm.error ? <ErrorState message={farm.error} /> : farm.data && (
        <FarmForm farm={farm.data} onSaved={async (f) => { await reload(); router.push(`/app/farms/${f.id}`); }} />
      )}
    </div>
  );
}
