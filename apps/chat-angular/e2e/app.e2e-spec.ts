import { ChatAngularPage } from './app.po';

describe('chat-angular App', () => {
  let page: ChatAngularPage;

  beforeEach(() => {
    page = new ChatAngularPage();
  });

  it('should display welcome message', () => {
    page.navigateTo();
    expect(page.getParagraphText()).toEqual('Welcome to app!');
  });
});
