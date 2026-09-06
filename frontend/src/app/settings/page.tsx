import SourceUrlManager from "@/components/SourceUrlManager";

export default function SettingsPage() {
  return (
    <>
      <div className="topbar">
        <div>
          <h1>Configuración</h1>
          <p>Administra las fuentes que usa el pipeline de investigación.</p>
        </div>
      </div>
      <SourceUrlManager />
    </>
  );
}
