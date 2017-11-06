import { AdminAngularPage } from './app.po';

describe('admin-angular App', () => {
  let page: AdminAngularPage;

  beforeEach(() => {
    page = new AdminAngularPage();
  });

  it('should display welcome message', () => {
    page.navigateTo();
    expect(page.getParagraphText()).toEqual('Welcome to app!');
  });
});
