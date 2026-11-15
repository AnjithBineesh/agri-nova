"use client";

import { useRouter } from "next/navigation";
import FarmForm from "@/components/FarmForm";
import { PageHeader } from "@/components/ui";
import { useFarm } from "@/lib/farm";

export default function NewFarmPage() {
  const router = useRouter();
  const { reload, selectFarm } = useFarm();
  return (
    <div>
      <PageHeader tag="New farm" title="Add a" accent="farm" intro="Only the location and a name are required. Everything else improves the recommendations and can be added later." />
      <FarmForm onSaved={async (f) => {
        await reload();
        selectFarm(f.id);
        router.push(`/app/earth?new=1`);
      }} />
    </div>
  );
}
