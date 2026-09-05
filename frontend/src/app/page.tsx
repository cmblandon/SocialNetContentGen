import Link from "next/link";

export default function Home() {
  return (
    <main>
      <h1>Archivo Desclasificado — Admin Panel</h1>
      <nav>
        <ul>
          <li>
            <Link href="/approvals">Approval Queue</Link>
          </li>
          <li>
            <Link href="/calendar">Editorial Calendar</Link>
          </li>
          <li>
            <Link href="/cases">Covered Cases</Link>
          </li>
        </ul>
      </nav>
    </main>
  );
}
