import SalonTabBar from '../navigation/SalonTabBar';

export default function SalonProfilePage() {
  const salonName = localStorage.getItem('fixme_provider_name') || 'Salon Profile';

  return (
    <div className="min-h-screen bg-fixme-bg pb-24 px-4 pt-8 max-w-md mx-auto">
      <h1 className="text-fixme-text-primary text-2xl font-bold">{salonName}</h1>
      <p className="text-fixme-text-secondary text-sm mt-2">
        Salon perspective profile with linked freelancers and team context.
      </p>

      <div className="mt-4 flex gap-2">
        <button
          onClick={() => { window.location.href = '/salon/home'; }}
          className="bg-fixme-card border border-fixme-border text-fixme-text-secondary text-sm font-semibold px-4 py-2 rounded-xl"
        >
          Open Salon Home
        </button>
        <button
          onClick={() => { window.location.href = '/salon/settings'; }}
          className="bg-fixme-accent text-fixme-bg text-sm font-semibold px-4 py-2 rounded-xl"
        >
          Edit Salon Settings
        </button>
      </div>

      <SalonTabBar active="profile" />
    </div>
  );
}
