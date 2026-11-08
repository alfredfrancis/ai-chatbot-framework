import { Link, useNavigate } from "react-router-dom";
import { PageHeader, Topbar, useApp } from "../App";
import { IconApp, IconPlus } from "../components/icons";

export const CREATE_APP_PROMPT = "I want to build an app using the personal-apps skill. Interview me about my app requirements.";

export default function AppsPage() {
  const { apps } = useApp();
  const navigate = useNavigate();
  const create = () => navigate("/", { state: { draft: CREATE_APP_PROMPT } });

  return (
    <>
      <Topbar title="Your apps" phoneOnly />
      <div className="page">
        <div className="page-inner">
          <PageHeader title="Your apps" lead="Apps your agent built for you. Open one, or create a new one by describing it in a chat.">
            <button className="btn primary" onClick={create}><IconPlus />Create app</button>
          </PageHeader>
          <div className="list">
            {apps.length === 0 && <div className="empty">No apps yet. Create one and the agent will ask what it should do.</div>}
            {apps.map((a) => (
              <Link className="lrow" key={a.id} to={`/apps/${a.id}`} data-testid={`app-${a.id}`}>
                <div className="tile" aria-hidden="true"><IconApp /></div>
                <div className="grow">
                  <span className="title">{a.title}</span>
                  {(a.error || a.description) && <span className="meta">{a.error ? "Needs fixing" : a.description}</span>}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
